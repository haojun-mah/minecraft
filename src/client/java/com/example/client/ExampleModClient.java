package com.example.client;

import com.example.network.BuildProgressPayload;
import com.mojang.blaze3d.platform.InputConstants;
import net.fabricmc.api.ClientModInitializer;
import net.fabricmc.fabric.api.client.event.lifecycle.v1.ClientTickEvents;
import net.fabricmc.fabric.api.client.keybinding.v1.KeyBindingHelper;
import net.fabricmc.fabric.api.client.networking.v1.ClientPlayNetworking;
import net.minecraft.client.KeyMapping;
import org.lwjgl.glfw.GLFW;

public class ExampleModClient implements ClientModInitializer {

    public static KeyMapping openArchitectKey;

    @Override
    public void onInitializeClient() {
        // Register G keybind under "AI Architect" category
        openArchitectKey = KeyBindingHelper.registerKeyBinding(new KeyMapping(
                "key.modid.open_architect",
                InputConstants.Type.KEYSYM,
                GLFW.GLFW_KEY_G,
                "category.modid.architect"
        ));

        // Open the screen when G is pressed in-game
        ClientTickEvents.END_CLIENT_TICK.register(client -> {
            if (openArchitectKey.consumeClick() && client.screen == null) {
                client.setScreen(new ArchitectScreen());
            }
        });

        // Stream progress updates from the server to the open screen
        ClientPlayNetworking.registerGlobalReceiver(BuildProgressPayload.TYPE, (payload, context) ->
                context.client().execute(() -> {
                    if (context.client().screen instanceof ArchitectScreen screen) {
                        screen.onProgress(payload.placed(), payload.total(), payload.done());
                    }
                })
        );
    }
}
