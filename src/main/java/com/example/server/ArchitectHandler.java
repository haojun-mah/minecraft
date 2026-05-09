package com.example.server;

import com.example.ExampleMod;
import com.example.network.BuildBlockEntry;
import com.example.network.BuildBlocksPayload;
import com.example.network.BuildProgressPayload;
import net.fabricmc.fabric.api.networking.v1.ServerPlayNetworking;
import net.minecraft.core.BlockPos;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.phys.Vec3;

import java.util.ArrayList;
import java.util.List;
import java.util.Optional;
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
     * Receives the block list from the client (which got it from the AI backend)
     * and places each block in the world one at a time, streaming progress back.
     *
     * Blocks are placed relative to 5 blocks ahead of the player's look direction.
     */
    public static void handle(BuildBlocksPayload payload, ServerPlayNetworking.Context context) {
        ServerPlayer player = context.player();

        if (payload.blocks().isEmpty()) {
            ExampleMod.LOGGER.warn("[AI Architect] Received empty block list — nothing to place.");
            return;
        }

        ExampleMod.LOGGER.info("[AI Architect] Placing {} blocks for {}",
                payload.blocks().size(), player.getName().getString());

        // Anchor point: 5 blocks in front of where the player is looking
        Vec3 look  = player.getLookAngle();
        int baseX  = (int) Math.round(player.getX() + look.x * 5);
        int baseY  = (int) player.getY();
        int baseZ  = (int) Math.round(player.getZ() + look.z * 5);

        List<PlacedBlock> resolved = resolve(payload.blocks(), baseX, baseY, baseZ);
        placeSequentially(player, resolved);
    }

    // -------------------------------------------------------------------------

    private static List<PlacedBlock> resolve(
            List<BuildBlockEntry> entries, int baseX, int baseY, int baseZ) {

        List<PlacedBlock> out = new ArrayList<>(entries.size());
        for (BuildBlockEntry e : entries) {
            BlockPos pos   = new BlockPos(baseX + e.x(), baseY + e.y(), baseZ + e.z());
            Block    block = lookupBlock(e.block());
            out.add(new PlacedBlock(pos, block));
        }
        return out;
    }

    /** Looks up a block by full registry name; falls back to stone bricks on unknown IDs. */
    private static Block lookupBlock(String name) {
        String full = name.contains(":") ? name : "minecraft:" + name;
        ResourceLocation id = ResourceLocation.tryParse(full);
        if (id == null) return Blocks.STONE_BRICKS;
        Optional<Block> found = BuiltInRegistries.BLOCK.getOptional(id);
        return found.orElse(Blocks.STONE_BRICKS);
    }

    private static void placeSequentially(ServerPlayer player, List<PlacedBlock> blocks) {
        ServerLevel level = (ServerLevel) player.level();
        int total = blocks.size();

        for (int i = 0; i < total; i++) {
            final int       idx   = i;
            final PlacedBlock entry = blocks.get(idx);

            SCHEDULER.schedule(
                    () -> level.getServer().execute(() -> {
                        level.setBlock(entry.pos(), entry.block().defaultBlockState(), 3);
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
