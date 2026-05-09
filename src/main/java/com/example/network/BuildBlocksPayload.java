package com.example.network;

import net.minecraft.network.RegistryFriendlyByteBuf;
import net.minecraft.network.codec.StreamCodec;
import net.minecraft.network.protocol.common.custom.CustomPacketPayload;
import net.minecraft.resources.Identifier;

import java.util.ArrayList;
import java.util.List;

public record BuildBlocksPayload(List<BuildBlockEntry> blocks, boolean preview)
        implements CustomPacketPayload {

    public static final Type<BuildBlocksPayload> TYPE =
            new Type<>(Identifier.fromNamespaceAndPath("modid", "build_blocks"));

    public static final StreamCodec<RegistryFriendlyByteBuf, BuildBlocksPayload> CODEC =
            StreamCodec.ofMember(
                    (payload, buf) -> {
                        buf.writeBoolean(payload.preview());
                        buf.writeVarInt(payload.blocks().size());
                        for (BuildBlockEntry e : payload.blocks()) {
                            buf.writeVarInt(e.x());
                            buf.writeVarInt(e.y());
                            buf.writeVarInt(e.z());
                            buf.writeUtf(e.block(), 256);
                        }
                    },
                    buf -> {
                        boolean preview = buf.readBoolean();
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
                        return new BuildBlocksPayload(list, preview);
                    }
            );

    @Override
    public Type<? extends CustomPacketPayload> type() { return TYPE; }
}
