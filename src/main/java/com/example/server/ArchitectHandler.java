package com.example.server;

import com.example.ExampleMod;
import com.example.network.BuildBlockEntry;
import com.example.network.BuildBlocksPayload;
import com.example.network.BuildProgressPayload;
import net.fabricmc.fabric.api.networking.v1.ServerPlayNetworking;
import net.minecraft.core.BlockPos;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.resources.Identifier;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.Blocks;

import java.util.ArrayList;
import java.util.List;
import java.util.Optional;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;

public class ArchitectHandler {

    // Tracks ghost-preview block positions per player so they can be cleared.
    private static final ConcurrentHashMap<UUID, List<BlockPos>> PREVIEWS = new ConcurrentHashMap<>();

    public static void handle(BuildBlocksPayload payload, ServerPlayNetworking.Context context) {
        ServerPlayer player = context.player();
        ServerLevel  level  = (ServerLevel) player.level();

        if (payload.blocks().isEmpty()) {
            ExampleMod.LOGGER.warn("[AI Architect] Received empty block list.");
            return;
        }

        List<PlacedBlock> resolved = resolve(payload.blocks());

        if (payload.preview()) {
            showPreview(player, level, resolved);
        } else {
            clearPreview(player, level);
            placeInstantly(player, resolved);
        }
    }

    // -------------------------------------------------------------------------
    // Preview — instant lime-glass ghost, clears the previous one first

    private static void showPreview(ServerPlayer player, ServerLevel level,
                                    List<PlacedBlock> blocks) {
        clearPreview(player, level);
        List<BlockPos> positions = new ArrayList<>(blocks.size());
        for (PlacedBlock pb : blocks) {
            level.setBlock(pb.pos(), Blocks.LIGHT_BLUE_STAINED_GLASS.defaultBlockState(), 3);
            positions.add(pb.pos());
        }
        PREVIEWS.put(player.getUUID(), positions);
        ExampleMod.LOGGER.info("[AI Architect] Preview: {} blocks for {}",
                blocks.size(), player.getName().getString());
    }

    private static void clearPreview(ServerPlayer player, ServerLevel level) {
        List<BlockPos> old = PREVIEWS.remove(player.getUUID());
        if (old != null) {
            for (BlockPos pos : old)
                level.setBlock(pos, Blocks.AIR.defaultBlockState(), 3);
        }
    }

    // -------------------------------------------------------------------------
    // Real placement — one block every 40 ms with progress packets

    private static List<PlacedBlock> resolve(List<BuildBlockEntry> entries) {
        List<PlacedBlock> out = new ArrayList<>(entries.size());
        for (BuildBlockEntry e : entries)
            out.add(new PlacedBlock(new BlockPos(e.x(), e.y(), e.z()), lookupBlock(e.block())));
        return out;
    }

    private static Block lookupBlock(String name) {
        String full = name.contains(":") ? name : "minecraft:" + name;
        Identifier id = Identifier.tryParse(full);
        if (id == null) return Blocks.STONE_BRICKS;
        Optional<Block> found = BuiltInRegistries.BLOCK.getOptional(id);
        return found.orElse(Blocks.STONE_BRICKS);
    }

    private static void placeInstantly(ServerPlayer player, List<PlacedBlock> blocks) {
        ServerLevel level = (ServerLevel) player.level();
        int total = blocks.size();
        level.getServer().execute(() -> {
            for (PlacedBlock pb : blocks)
                level.setBlock(pb.pos(), pb.block().defaultBlockState(), 3);
            ServerPlayNetworking.send(player, new BuildProgressPayload(total, total, true));
        });
    }

    private record PlacedBlock(BlockPos pos, Block block) {}
}
