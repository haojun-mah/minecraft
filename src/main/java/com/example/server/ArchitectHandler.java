package com.example.server;

import com.example.ExampleMod;
import com.example.network.BuildProgressPayload;
import com.example.network.BuildRequestPayload;
import net.fabricmc.fabric.api.networking.v1.ServerPlayNetworking;
import net.minecraft.block.Block;
import net.minecraft.block.Blocks;
import net.minecraft.server.network.ServerPlayerEntity;
import net.minecraft.server.world.ServerWorld;
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

    public static void handle(BuildRequestPayload payload, ServerPlayNetworking.Context context) {
        ServerPlayerEntity player = context.player();
        ExampleMod.LOGGER.info("[AI Architect] Build request: \"{}\"", payload.prompt());

        // TODO: Replace this stub with a real AI API call.
        // The AI should return a List<PlacedBlock> where each entry has a BlockPos and Block type.
        List<PlacedBlock> blocks = stubGenerateStructure(player, payload.prompt());

        placeBlocksSequentially(player, blocks);
    }

    // -------------------------------------------------------------------------
    // Stub structure — replace with AI-generated block list
    // -------------------------------------------------------------------------

    private static List<PlacedBlock> stubGenerateStructure(ServerPlayerEntity player, String prompt) {
        Block material = pickMaterial(prompt);

        // Place structure 6 blocks in front of where the player is looking
        Vec3d look = player.getRotationVec(1.0f);
        int baseX = (int) Math.round(player.getX() + look.x * 8);
        int baseY = (int) player.getY();
        int baseZ = (int) Math.round(player.getZ() + look.z * 8);

        List<PlacedBlock> positions = new ArrayList<>();
        int w = 7, h = 9;

        for (int y = 0; y < h; y++) {
            for (int x = 0; x < w; x++) {
                for (int z = 0; z < w; z++) {
                    boolean onWall = x == 0 || x == w - 1 || z == 0 || z == w - 1;
                    if (!onWall) continue;

                    // Battlements: skip every other block on the top row
                    if (y == h - 1 && (x + z) % 2 == 0) continue;

                    positions.add(new PlacedBlock(
                            new BlockPos(baseX + x, baseY + y, baseZ + z),
                            material
                    ));
                }
            }
        }
        return positions;
    }

    private static Block pickMaterial(String prompt) {
        String p = prompt.toLowerCase();
        if (p.contains("sand") || p.contains("desert")) return Blocks.SANDSTONE;
        if (p.contains("wood") || p.contains("house") || p.contains("cabin")) return Blocks.OAK_PLANKS;
        if (p.contains("dark") || p.contains("nether")) return Blocks.NETHER_BRICKS;
        if (p.contains("snow") || p.contains("ice")) return Blocks.PACKED_ICE;
        return Blocks.STONE_BRICKS; // default: medieval stone
    }

    // -------------------------------------------------------------------------
    // Block-by-block placement with progress packets
    // -------------------------------------------------------------------------

    private static void placeBlocksSequentially(ServerPlayerEntity player, List<PlacedBlock> blocks) {
        ServerWorld world = player.getServerWorld();
        int total = blocks.size();

        for (int i = 0; i < total; i++) {
            final int idx = i;
            final PlacedBlock entry = blocks.get(idx);
            SCHEDULER.schedule(() ->
                world.getServer().execute(() -> {
                    world.setBlockState(entry.pos(), entry.block().getDefaultState());
                    ServerPlayNetworking.send(player, new BuildProgressPayload(
                            idx + 1, total, idx == total - 1
                    ));
                }),
                idx * 40L, TimeUnit.MILLISECONDS
            );
        }
    }

    public record PlacedBlock(BlockPos pos, Block block) {}
}
