package com.example.client;

import com.example.network.BuildBlockEntry;
import com.example.network.BuildBlocksPayload;
import net.fabricmc.fabric.api.client.networking.v1.ClientPlayNetworking;
import net.minecraft.client.gui.GuiGraphicsExtractor;
import net.minecraft.client.gui.components.Button;
import net.minecraft.client.gui.components.EditBox;
import net.minecraft.client.gui.screens.Screen;
import net.minecraft.client.input.KeyEvent;
import net.minecraft.core.BlockPos;
import net.minecraft.network.chat.Component;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.Collections;
import java.util.List;

public class ArchitectScreen extends Screen {

    private static final int PANEL_W = 340;
    private static final int PANEL_H = 185;
    private static final int ACCENT  = 0xFF5566FF;
    private static final int BG      = 0xDD000000;

    // Field width, button width, gap — kept as constants for layout math
    private static final int FW = 69;   // coord field width
    private static final int BW = 14;   // nudge button width
    private static final int GW = BW + 2 + FW + 2 + BW; // group width = 101
    private static final int GAP = 8;   // gap between groups

    private EditBox promptField;
    private EditBox xField, yField, zField;
    private Button  previewButton, placeButton;

    private String  statusMessage = "";
    private int     placed = 0, total = 0;
    private boolean generating = false;
    private String  cachedPrompt = "";
    private List<BuildBlockEntry> cachedRelativeBlocks = List.of();

    public ArchitectScreen() {
        super(Component.literal("AI Architect"));
    }

    // -------------------------------------------------------------------------
    // Init
    // -------------------------------------------------------------------------

    @Override
    protected void init() {
        int px = (width  - PANEL_W) / 2;
        int py = (height - PANEL_H) / 2;

        // Prompt field
        promptField = new EditBox(font, px + 10, py + 36, PANEL_W - 20, 20,
                Component.literal("prompt"));
        promptField.setMaxLength(256);
        promptField.setHint(Component.literal("e.g. medieval castle, cosy wood cabin..."));
        addRenderableWidget(promptField);

        // X / Y / Z fields — prefer ghost origin (crosshair target) when available
        BlockPos ghostOrigin = GhostPreview.isActive() ? GhostPreview.getOrigin() : null;
        int bx = ghostOrigin != null ? ghostOrigin.getX() : (minecraft.player != null ? minecraft.player.getBlockX() : 0);
        int by = ghostOrigin != null ? ghostOrigin.getY() : (minecraft.player != null ? minecraft.player.getBlockY() : 64);
        int bz = ghostOrigin != null ? ghostOrigin.getZ() : (minecraft.player != null ? minecraft.player.getBlockZ() : 0);

        xField = buildCoordGroup(px, py + 72, 0, bx);
        yField = buildCoordGroup(px, py + 72, 1, by);
        zField = buildCoordGroup(px, py + 72, 2, bz);

        // Preview / Place buttons
        int btnW = (PANEL_W - 30) / 2;   // ~155 px each
        previewButton = Button.builder(Component.literal("Preview"), btn -> sendBlocks(true))
                .bounds(px + 10, py + 102, btnW, 20)
                .build();
        placeButton = Button.builder(Component.literal("Place"), btn -> sendBlocks(false))
                .bounds(px + 20 + btnW, py + 102, btnW, 20)
                .build();
        addRenderableWidget(previewButton);
        addRenderableWidget(placeButton);

        setInitialFocus(promptField);
        promptField.setFocused(true);
    }

    /** Adds [-] [field] [+] for one axis and returns the EditBox. */
    private EditBox buildCoordGroup(int panelX, int fieldY, int groupIndex, int value) {
        int gx = panelX + 10 + groupIndex * (GW + GAP);

        addRenderableWidget(Button.builder(Component.literal("<"),
                        b -> nudge(groupIndex, -1))
                .bounds(gx, fieldY, BW, 20).build());

        EditBox field = new EditBox(font, gx + BW + 2, fieldY, FW, 20, Component.empty());
        field.setMaxLength(8);
        field.setValue(String.valueOf(value));
        addRenderableWidget(field);

        addRenderableWidget(Button.builder(Component.literal(">"),
                        b -> nudge(groupIndex, +1))
                .bounds(gx + BW + 2 + FW + 2, fieldY, BW, 20).build());

        return field;
    }

    // -------------------------------------------------------------------------
    // Logic
    // -------------------------------------------------------------------------

    /** Nudge one axis by delta and re-send a preview automatically. */
    private void nudge(int axis, int delta) {
        EditBox f = axis == 0 ? xField : axis == 1 ? yField : zField;
        try {
            f.setValue(String.valueOf(Integer.parseInt(f.getValue().trim()) + delta));
        } catch (NumberFormatException ignored) {}
        sendBlocks(true);   // auto re-preview on nudge
    }

    private void sendBlocks(boolean preview) {
        if (generating) return;

        String prompt = promptField.getValue().trim();
        if (prompt.isEmpty()) {
            statusMessage = "Error: prompt cannot be empty";
            return;
        }

        int tx, ty, tz;
        try {
            tx = Integer.parseInt(xField.getValue().trim());
            ty = Integer.parseInt(yField.getValue().trim());
            tz = Integer.parseInt(zField.getValue().trim());
        } catch (NumberFormatException e) {
            statusMessage = "Error: X/Y/Z must be integers";
            return;
        }

        if (prompt.equals(cachedPrompt) && !cachedRelativeBlocks.isEmpty()) {
            applyGeneratedBlocks(cachedRelativeBlocks, tx, ty, tz, preview);
        } else {
            requestBlocks(prompt, tx, ty, tz, preview);
        }
    }

    private void requestBlocks(String prompt, int tx, int ty, int tz, boolean preview) {
        generating = true;
        setButtonsEnabled(false);
        statusMessage = preview ? "Generating preview..." : "Generating build...";
        placed = 0;
        total = 0;

        if (minecraft == null) {
            generating = false;
            setButtonsEnabled(true);
            statusMessage = "Minecraft client unavailable";
            return;
        }

        BackendClient.generateBlocks(prompt).whenComplete((blocks, error) -> minecraft.execute(() -> {
            if (error != null) {
                generating = false;
                setButtonsEnabled(true);
                statusMessage = formatError(error);
                return;
            }

            if (blocks.isEmpty()) {
                generating = false;
                setButtonsEnabled(true);
                statusMessage = "Backend returned no blocks";
                return;
            }

            cachedPrompt = prompt;
            cachedRelativeBlocks = List.copyOf(blocks);
            applyGeneratedBlocks(cachedRelativeBlocks, tx, ty, tz, preview);
        }));
    }

    private void applyGeneratedBlocks(List<BuildBlockEntry> relativeBlocks, int tx, int ty, int tz, boolean preview) {
        List<BuildBlockEntry> absoluteBlocks = translateBlocks(relativeBlocks, tx, ty, tz);
        if (preview) {
            BlockPos anchor = minPos(absoluteBlocks);
            GhostPreview.setShape(absoluteBlocks);
            GhostPreview.setOrigin(anchor);
            generating = false;
            setButtonsEnabled(true);
            statusMessage = "Preview ready — close screen to drag";
        } else {
            startPlacement(absoluteBlocks);
        }
    }

    private void startPlacement(List<BuildBlockEntry> blocks) {
        GhostPreview.clear();
        generating = true;
        setButtonsEnabled(false);
        statusMessage = "Placing...";
        placed = 0;
        total = blocks.size();
        ClientPlayNetworking.send(new BuildBlocksPayload(blocks, false));
    }

    private void setButtonsEnabled(boolean enabled) {
        previewButton.active = enabled;
        placeButton.active = enabled;
    }

    private static List<BuildBlockEntry> translateBlocks(List<BuildBlockEntry> blocks, int ox, int oy, int oz) {
        List<BuildBlockEntry> translated = new ArrayList<>(blocks.size());
        for (BuildBlockEntry block : blocks) {
            translated.add(new BuildBlockEntry(
                    ox + block.x(),
                    oy + block.y(),
                    oz + block.z(),
                    block.block()
            ));
        }
        return translated;
    }

    private static BlockPos minPos(List<BuildBlockEntry> blocks) {
        BuildBlockEntry min = Collections.min(
                blocks,
                Comparator.comparingInt(BuildBlockEntry::x)
                        .thenComparingInt(BuildBlockEntry::y)
                        .thenComparingInt(BuildBlockEntry::z)
        );
        return new BlockPos(min.x(), min.y(), min.z());
    }

    private static String formatError(Throwable error) {
        Throwable current = error;
        while (current.getCause() != null) {
            current = current.getCause();
        }
        String message = current.getMessage();
        return (message == null || message.isBlank()) ? "Backend request failed" : message;
    }

    // -------------------------------------------------------------------------
    // Progress callbacks
    // -------------------------------------------------------------------------

    public void onProgress(int placed, int total, boolean done) {
        this.placed = placed;
        this.total  = total;
        if (done) {
            generating           = false;
            statusMessage        = "Done! Placed " + total + " blocks.";
            placeButton.active   = true;
            previewButton.active = true;
        } else {
            statusMessage = "Placing... " + placed + "/" + total;
        }
    }

    // -------------------------------------------------------------------------
    // Rendering
    // -------------------------------------------------------------------------

    @Override
    public void extractRenderState(GuiGraphicsExtractor g, int mx, int my, float delta) {
        int px = (width  - PANEL_W) / 2;
        int py = (height - PANEL_H) / 2;

        g.fill(px, py, px + PANEL_W, py + PANEL_H, BG);
        border(g, px, py, PANEL_W, PANEL_H, ACCENT);

        g.fill(px, py, px + PANEL_W, py + 18, ACCENT);
        g.centeredText(font, title, width / 2, py + 5, 0xFFFFFF);

        g.text(font, "Describe your structure:", px + 10, py + 26, 0xCCCCCC);

        // Axis labels centred over each coord group
        for (int i = 0; i < 3; i++) {
            String label = i == 0 ? "X" : i == 1 ? "Y" : "Z";
            int cx = px + 10 + i * (GW + GAP) + GW / 2;
            g.centeredText(font, label, cx, py + 62, 0xAAAAAA);
        }

        super.extractRenderState(g, mx, my, delta);  // widgets

        if (!statusMessage.isEmpty())
            g.centeredText(font, statusMessage, width / 2, py + 132, 0xAAAAAA);

        if (total > 0) {
            int bx = px + 10, by = py + 145, bw = PANEL_W - 20;
            int filled = (int) ((float) placed / total * bw);
            g.fill(bx, by, bx + bw, by + 6, 0xFF222222);
            g.fill(bx, by, bx + filled, by + 6, ACCENT);
            if (filled > 0 && filled < bw)
                g.fill(bx + filled, by, bx + filled + 1, by + 6, 0xFFFFFFFF);
        }
    }

    private static void border(GuiGraphicsExtractor g, int x, int y, int w, int h, int c) {
        g.fill(x,         y,         x + w, y + 1,  c);
        g.fill(x,         y + h - 1, x + w, y + h,  c);
        g.fill(x,         y,         x + 1, y + h,  c);
        g.fill(x + w - 1, y,         x + w, y + h,  c);
    }

    @Override
    public boolean keyPressed(KeyEvent event) {
        int key = event.key();
        if ((key == 257 || key == 335) && !generating) { sendBlocks(false); return true; }
        return super.keyPressed(event);
    }

    @Override
    public boolean isPauseScreen() { return false; }
}
