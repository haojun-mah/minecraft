package com.example.client;

import com.example.network.BuildProgressPayload;
import com.mojang.blaze3d.platform.InputConstants;
import net.fabricmc.api.ClientModInitializer;
import net.fabricmc.fabric.api.client.event.lifecycle.v1.ClientTickEvents;
import net.fabricmc.fabric.api.client.keymapping.v1.KeyMappingHelper;
import net.fabricmc.fabric.api.client.networking.v1.ClientPlayNetworking;
import net.minecraft.client.KeyMapping;
import org.lwjgl.glfw.GLFW;

public class ExampleModClient implements ClientModInitializer {

    public static KeyMapping openArchitectKey;

    @Override
    public void onInitializeClient() {
        openArchitectKey = KeyMappingHelper.registerKeyMapping(new KeyMapping(
                "key.modid.open_architect",
                InputConstants.Type.KEYSYM,
                GLFW.GLFW_KEY_G,
                KeyMapping.Category.MISC
        ));

        GhostPreview.register();
        BuildHud.register();

        ClientTickEvents.END_CLIENT_TICK.register(client -> {
            GhostPreview.tick(client);
            if (openArchitectKey.consumeClick() && client.screen == null) {
                client.setScreen(new ArchitectScreen());
            }
        });

        ClientPlayNetworking.registerGlobalReceiver(BuildProgressPayload.TYPE, (payload, context) ->
                context.client().execute(() -> {
                    // Always update global state (HUD works even when screen is closed)
                    BuildState.INSTANCE.updatePlacement(payload.placed(), payload.total(), payload.done());

                    // Also update the screen if it is open
                    if (context.client().screen instanceof ArchitectScreen screen) {
                        screen.onProgress(payload.placed(), payload.total(), payload.done());
                    }
                })
        );
    }
}
