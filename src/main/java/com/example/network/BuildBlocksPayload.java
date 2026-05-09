package com.example.network;

import net.minecraft.network.RegistryFriendlyByteBuf;
import net.minecraft.network.codec.StreamCodec;
import net.minecraft.network.protocol.common.custom.CustomPacketPayload;
import net.minecraft.resources.ResourceLocation;

import java.util.ArrayList;
import java.util.List;

/**
 * Client → Server: the AI-generated block list for the server to place.
 *
 * Expected backend JSON (sent back to ArchitectScreen over HTTP):
 *   [{"x":0,"y":0,"z":0,"block":"minecraft:stone_bricks"}, ...]
 * or {"blocks":[...]}
 *
 * x/y/z are relative to the player's position when Generate was pressed.
 */
public record BuildBlocksPayload(List<BuildBlockEntry> blocks)
        implements CustomPacketPayload {

    public static final Type<BuildBlocksPayload> TYPE =
            new Type<>(ResourceLocation.fromNamespaceAndPath("modid", "build_blocks"));

    public static final StreamCodec<RegistryFriendlyByteBuf, BuildBlocksPayload> CODEC =
            StreamCodec.ofMember(
                    (buf, payload) -> {
                        buf.writeVarInt(payload.blocks().size());
                        for (BuildBlockEntry e : payload.blocks()) {
                            buf.writeVarInt(e.x());
                            buf.writeVarInt(e.y());
                            buf.writeVarInt(e.z());
                            buf.writeUtf(e.block(), 256);
                        }
                    },
                    buf -> {
                        int size = buf.readVarInt();
                        List<BuildBlockEntry> list = new ArrayList<>(size);
                        for (int i = 0; i < size; i++) {
                            list.add(new BuildBlockEntry(
                                    buf.readVarInt(),
                                    buf.readVarInt(),
                                    buf.readVarInt(),
                                    buf.readUtf(256)
                            ));
                        }
                        return new BuildBlocksPayload(list);
                    }
            );

    @Override
    public Type<? extends CustomPacketPayload> type() {
        return TYPE;
    }
}
