package com.example;

import com.example.network.BuildBlocksPayload;
import com.example.network.BuildProgressPayload;
import com.example.server.ArchitectHandler;
import net.fabricmc.api.ModInitializer;
import net.fabricmc.fabric.api.networking.v1.PayloadTypeRegistry;
import net.fabricmc.fabric.api.networking.v1.ServerPlayNetworking;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

public class ExampleMod implements ModInitializer {

    public static final String MOD_ID = "modid";
    public static final Logger LOGGER = LoggerFactory.getLogger(MOD_ID);

    @Override
    public void onInitialize() {
        PayloadTypeRegistry.playC2S().register(BuildBlocksPayload.ID,  BuildBlocksPayload.CODEC);
        PayloadTypeRegistry.playS2C().register(BuildProgressPayload.ID, BuildProgressPayload.CODEC);

        ServerPlayNetworking.registerGlobalReceiver(BuildBlocksPayload.ID, ArchitectHandler::handle);

        LOGGER.info("[AI Architect] Mod initialised.");
    }
}
