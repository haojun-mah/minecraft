package com.example.client;

import net.fabricmc.fabric.api.client.rendering.v1.hud.HudElement;
import net.fabricmc.fabric.api.client.rendering.v1.hud.HudElementRegistry;
import net.minecraft.client.DeltaTracker;
import net.minecraft.client.Minecraft;
import net.minecraft.client.gui.GuiGraphicsExtractor;
import net.minecraft.resources.Identifier;

public final class BuildHud implements HudElement {

    private static final Identifier ID     = Identifier.fromNamespaceAndPath("modid", "build_progress");
    private static final int        ACCENT = 0xFF5566FF;
    private static final int        BG     = 0xBB000000;

    private BuildHud() {}

    public static void register() {
        HudElementRegistry.addLast(ID, new BuildHud());
    }

    @Override
    public void extractRenderState(GuiGraphicsExtractor g, DeltaTracker delta) {
        Minecraft mc = Minecraft.getInstance();
        if (mc.screen instanceof ArchitectScreen) return;

        BuildState state = BuildState.INSTANCE;
        String msg = state.getStatusMessage();
        if (msg.isEmpty()) return;

        int sw = mc.getWindow().getGuiScaledWidth();

        // Progress bar strip at very top
        float progress = state.getOverallProgress();
        int filled = (int) (progress * sw);
        g.fill(0, 0, sw, 3, 0xFF222222);
        if (filled > 0)
            g.fill(0, 0, filled, 3, ACCENT);

        // Stage label just below the bar
        g.fill(0, 3, sw, 16, BG);
        g.centeredText(mc.font, msg, sw / 2, 4, 0xFFFFFF);
    }
}
