package com.example.network;

import net.minecraft.network.PacketByteBuf;
import net.minecraft.network.codec.PacketCodec;
import net.minecraft.network.codec.PacketCodecs;
import net.minecraft.network.packet.CustomPayload;
import net.minecraft.util.Identifier;

public record BuildRequestPayload(String prompt) implements CustomPayload {

    public static final Id<BuildRequestPayload> ID =
            new Id<>(Identifier.of("modid", "build_request"));

    public static final PacketCodec<PacketByteBuf, BuildRequestPayload> CODEC =
            PacketCodec.tuple(
                    PacketCodecs.string(512), BuildRequestPayload::prompt,
                    BuildRequestPayload::new
            );

    @Override
    public Id<? extends CustomPayload> getId() {
        return ID;
    }
}
