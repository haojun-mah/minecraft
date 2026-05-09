package com.example.network;

import net.minecraft.network.RegistryFriendlyByteBuf;
import net.minecraft.network.codec.StreamCodec;
import net.minecraft.network.protocol.common.custom.CustomPacketPayload;
import net.minecraft.resources.Identifier;

public record BuildProgressPayload(int placed, int total, boolean done)
        implements CustomPacketPayload {

    public static final Type<BuildProgressPayload> TYPE =
            new Type<>(Identifier.fromNamespaceAndPath("modid", "build_progress"));

    public static final StreamCodec<RegistryFriendlyByteBuf, BuildProgressPayload> CODEC =
            StreamCodec.ofMember(
                    (p, buf) -> {
                        buf.writeVarInt(p.placed());
                        buf.writeVarInt(p.total());
                        buf.writeBoolean(p.done());
                    },
                    buf -> new BuildProgressPayload(
                            buf.readVarInt(),
                            buf.readVarInt(),
                            buf.readBoolean()
                    )
            );

    @Override
    public Type<? extends CustomPacketPayload> type() {
        return TYPE;
    }
}
