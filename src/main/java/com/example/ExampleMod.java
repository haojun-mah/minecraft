package com.example;

import com.example.network.BuildProgressPayload;
import com.example.network.BuildRequestPayload;
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
        // Register packet types (must happen before any networking)
        PayloadTypeRegistry.playC2S().register(BuildRequestPayload.ID,  BuildRequestPayload.CODEC);
        PayloadTypeRegistry.playS2C().register(BuildProgressPayload.ID, BuildProgressPayload.CODEC);

        // Server receives the prompt and starts building
        ServerPlayNetworking.registerGlobalReceiver(BuildRequestPayload.ID, ArchitectHandler::handle);

        LOGGER.info("[AI Architect] Mod initialised.");
    }
}
