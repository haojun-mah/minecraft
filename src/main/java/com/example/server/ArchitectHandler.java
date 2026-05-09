package com.example.server;

import com.example.ExampleMod;
import com.example.network.BuildBlockEntry;
import com.example.network.BuildBlocksPayload;
import com.example.network.BuildProgressPayload;
import net.fabricmc.fabric.api.networking.v1.ServerPlayNetworking;
import net.minecraft.block.Block;
import net.minecraft.block.Blocks;
import net.minecraft.registry.Registries;
import net.minecraft.server.network.ServerPlayerEntity;
import net.minecraft.server.world.ServerWorld;
import net.minecraft.util.Identifier;
import net.minecraft.util.math.BlockPos;
import net.minecraft.util.math.Vec3d;

import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.TimeUnit;

public class ArchitectHandler {

    private static final ScheduledExecutorService SCHEDULER =
            Executors.newSingleThreadScheduledExecutor(r -> {
                Thread t = new Thread(r, "architect-builder");
                t.setDaemon(true);
                return t;
            });

    /**
     * Receives the AI-generated block list from the client and places them
     * block by block in the world, sending progress packets back.
     *
     * Block coordinates are relative to the player's feet position + 5 blocks
     * in the direction they are looking.
     */
    public static void handle(BuildBlocksPayload payload, ServerPlayNetworking.Context context) {
        ServerPlayerEntity player = context.player();
        List<BuildBlockEntry> entries = payload.blocks();

        if (entries.isEmpty()) {
            ExampleMod.LOGGER.warn("[AI Architect] Received empty block list from client.");
            return;
        }

        ExampleMod.LOGGER.info("[AI Architect] Placing {} blocks for {}",
                entries.size(), player.getName().getString());

        // Anchor point: 5 blocks ahead of the player's look direction
        Vec3d look = player.getRotationVec(1.0f);
        int baseX = (int) Math.round(player.getX() + look.x * 5);
        int baseY = (int) player.getY();
        int baseZ = (int) Math.round(player.getZ() + look.z * 5);

        List<PlacedBlock> blocks = resolveBlocks(entries, baseX, baseY, baseZ);
        placeBlocksSequentially(player, blocks);
    }

    // -------------------------------------------------------------------------
    // Internal helpers
    // -------------------------------------------------------------------------

    private static List<PlacedBlock> resolveBlocks(
            List<BuildBlockEntry> entries, int baseX, int baseY, int baseZ) {

        List<PlacedBlock> out = new ArrayList<>(entries.size());
        for (BuildBlockEntry e : entries) {
            BlockPos pos = new BlockPos(baseX + e.x(), baseY + e.y(), baseZ + e.z());
            Block block = resolveBlock(e.block());
            out.add(new PlacedBlock(pos, block));
        }
        return out;
    }

    /** Looks up a block by its full registry name; falls back to stone bricks on unknown IDs. */
    private static Block resolveBlock(String registryName) {
        // Strip leading "minecraft:" if missing namespace
        String name = registryName.contains(":") ? registryName : "minecraft:" + registryName;
        Identifier id = Identifier.tryParse(name);
        if (id == null) return Blocks.STONE_BRICKS;
        Block block = Registries.BLOCK.get(id);
        return (block == Blocks.AIR && !name.equals("minecraft:air")) ? Blocks.STONE_BRICKS : block;
    }

    private static void placeBlocksSequentially(ServerPlayerEntity player, List<PlacedBlock> blocks) {
        ServerWorld world = player.getServerWorld();
        int total = blocks.size();

        for (int i = 0; i < total; i++) {
            final int idx = i;
            final PlacedBlock entry = blocks.get(idx);
            SCHEDULER.schedule(
                    () -> world.getServer().execute(() -> {
                        world.setBlockState(entry.pos(), entry.block().getDefaultState());
                        ServerPlayNetworking.send(player, new BuildProgressPayload(
                                idx + 1, total, idx == total - 1
                        ));
                    }),
                    idx * 40L, TimeUnit.MILLISECONDS
            );
        }
    }

    private record PlacedBlock(BlockPos pos, Block block) {}
}
