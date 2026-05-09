package com.example.network;

import net.minecraft.network.PacketByteBuf;
import net.minecraft.network.codec.PacketCodec;
import net.minecraft.network.codec.PacketCodecs;
import net.minecraft.network.packet.CustomPayload;
import net.minecraft.util.Identifier;

public record BuildProgressPayload(int placed, int total, boolean done) implements CustomPayload {

    public static final Id<BuildProgressPayload> ID =
            new Id<>(Identifier.of("modid", "build_progress"));

    public static final PacketCodec<PacketByteBuf, BuildProgressPayload> CODEC =
            PacketCodec.tuple(
                    PacketCodecs.VAR_INT, BuildProgressPayload::placed,
                    PacketCodecs.VAR_INT, BuildProgressPayload::total,
                    PacketCodecs.BOOL, BuildProgressPayload::done,
                    BuildProgressPayload::new
            );

    @Override
    public Id<? extends CustomPayload> getId() {
        return ID;
    }
}
