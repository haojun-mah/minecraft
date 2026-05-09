package com.example.client;

import com.example.network.BuildProgressPayload;
import net.fabricmc.api.ClientModInitializer;
import net.fabricmc.fabric.api.client.event.lifecycle.v1.ClientTickEvents;
import net.fabricmc.fabric.api.client.keybinding.v1.KeyBindingHelper;
import net.fabricmc.fabric.api.client.networking.v1.ClientPlayNetworking;
import net.minecraft.client.option.KeyBinding;
import net.minecraft.client.util.InputUtil;
import org.lwjgl.glfw.GLFW;

public class ExampleModClient implements ClientModInitializer {

    public static KeyBinding openArchitectKey;

    @Override
    public void onInitializeClient() {
        openArchitectKey = KeyBindingHelper.registerKeyBinding(new KeyBinding(
                "key.modid.open_architect",
                InputUtil.Type.KEYSYM,
                GLFW.GLFW_KEY_G,
                "category.modid.architect"
        ));

        // Open the screen when the hotkey is pressed
        ClientTickEvents.END_CLIENT_TICK.register(client -> {
            if (openArchitectKey.wasPressed() && client.currentScreen == null) {
                client.setScreen(new ArchitectScreen());
            }
        });

        // Forward build progress packets to the open ArchitectScreen
        ClientPlayNetworking.registerGlobalReceiver(BuildProgressPayload.ID, (payload, context) ->
                context.client().execute(() -> {
                    if (context.client().currentScreen instanceof ArchitectScreen screen) {
                        screen.onProgress(payload.placed(), payload.total(), payload.done());
                    }
                })
        );
    }
}
