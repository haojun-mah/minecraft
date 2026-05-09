package com.example.network;

import net.minecraft.network.PacketByteBuf;
import net.minecraft.network.codec.PacketCodec;
import net.minecraft.network.packet.CustomPayload;
import net.minecraft.util.Identifier;

import java.util.ArrayList;
import java.util.List;

/**
 * Client → Server: carry the AI-generated block list so the server can place them.
 *
 * Expected backend JSON format (array at root):
 * [
 *   {"x": 0, "y": 0, "z": 0, "block": "minecraft:stone_bricks"},
 *   ...
 * ]
 * Coordinates are relative to the player's position at build time.
 */
public record BuildBlocksPayload(List<BuildBlockEntry> blocks) implements CustomPayload {

    public static final Id<BuildBlocksPayload> ID =
            new Id<>(Identifier.of("modid", "build_blocks"));

    public static final PacketCodec<PacketByteBuf, BuildBlocksPayload> CODEC =
            PacketCodec.ofStatic(BuildBlocksPayload::encode, BuildBlocksPayload::decode);

    private static void encode(PacketByteBuf buf, BuildBlocksPayload payload) {
        buf.writeVarInt(payload.blocks().size());
        for (BuildBlockEntry e : payload.blocks()) {
            buf.writeVarInt(e.x());
            buf.writeVarInt(e.y());
            buf.writeVarInt(e.z());
            buf.writeString(e.block(), 256);
        }
    }

    private static BuildBlocksPayload decode(PacketByteBuf buf) {
        int size = buf.readVarInt();
        List<BuildBlockEntry> list = new ArrayList<>(size);
        for (int i = 0; i < size; i++) {
            list.add(new BuildBlockEntry(
                    buf.readVarInt(),
                    buf.readVarInt(),
                    buf.readVarInt(),
                    buf.readString(256)
            ));
        }
        return new BuildBlocksPayload(list);
    }

    @Override
    public Id<? extends CustomPayload> getId() {
        return ID;
    }
}
