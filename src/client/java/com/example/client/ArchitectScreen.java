package com.example.client;

import com.example.network.BuildBlockEntry;
import com.example.network.BuildBlocksPayload;
import net.fabricmc.fabric.api.client.networking.v1.ClientPlayNetworking;
import net.minecraft.client.Minecraft;
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
    private static final int PANEL_H = 215;
    private static final int ACCENT  = 0xFF5566FF;
    private static final int BG      = 0xDD000000;

    // Coord group constants
    private static final int FW  = 69;
    private static final int BW  = 14;
    private static final int GW  = BW + 2 + FW + 2 + BW;
    private static final int GAP = 8;

    // Size field constants
    private static final int SF_W  = 94;
    private static final int SF_GAP = 8;

    private EditBox promptField;
    private EditBox xField, yField, zField;
    private EditBox wField, hField, dField;
    private Button  previewButton, placeButton;

    boolean generating = false;  // package-private for BuildState callback access

    private String  statusMessage = "";
    private int     placed = 0, total = 0;
    private String  cachedPrompt = "";
    private List<BuildBlockEntry> cachedRelativeBlocks = List.of();

    public ArchitectScreen() {
        super(Component.literal("AI Architect"));
    }

    // -------------------------------------------------------------------------
    // Init

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

        // Sync prompt from previous session if still generating
        if (BuildState.INSTANCE.isActive()) {
            statusMessage = BuildState.INSTANCE.getStatusMessage();
            generating    = true;
            setButtonsEnabled(false);
        }

        // Origin X/Y/Z
        BlockPos ghostOrigin = GhostPreview.isActive() ? GhostPreview.getOrigin() : null;
        int bx = ghostOrigin != null ? ghostOrigin.getX() : (minecraft.player != null ? minecraft.player.getBlockX() : 0);
        int by = ghostOrigin != null ? ghostOrigin.getY() : (minecraft.player != null ? minecraft.player.getBlockY() : 64);
        int bz = ghostOrigin != null ? ghostOrigin.getZ() : (minecraft.player != null ? minecraft.player.getBlockZ() : 0);

        xField = buildCoordGroup(px, py + 72, 0, bx);
        yField = buildCoordGroup(px, py + 72, 1, by);
        zField = buildCoordGroup(px, py + 72, 2, bz);

        // Size W/H/D
        wField = buildSizeField(px + 10,                   py + 107, 32);
        hField = buildSizeField(px + 10 + SF_W + SF_GAP,   py + 107, 32);
        dField = buildSizeField(px + 10 + (SF_W + SF_GAP) * 2, py + 107, 32);

        // Buttons
        int btnW = (PANEL_W - 30) / 2;
        previewButton = Button.builder(Component.literal("Preview"), btn -> sendBlocks(true))
                .bounds(px + 10, py + 132, btnW, 20).build();
        placeButton = Button.builder(Component.literal("Place"), btn -> sendBlocks(false))
                .bounds(px + 20 + btnW, py + 132, btnW, 20).build();
        addRenderableWidget(previewButton);
        addRenderableWidget(placeButton);

        if (generating) setButtonsEnabled(false);

        setInitialFocus(promptField);
        promptField.setFocused(true);
    }

    private EditBox buildCoordGroup(int panelX, int fieldY, int groupIndex, int value) {
        int gx = panelX + 10 + groupIndex * (GW + GAP);
        addRenderableWidget(Button.builder(Component.literal("<"), b -> nudge(groupIndex, -1))
                .bounds(gx, fieldY, BW, 20).build());
        EditBox field = new EditBox(font, gx + BW + 2, fieldY, FW, 20, Component.empty());
        field.setMaxLength(8);
        field.setValue(String.valueOf(value));
        addRenderableWidget(field);
        addRenderableWidget(Button.builder(Component.literal(">"), b -> nudge(groupIndex, +1))
                .bounds(gx + BW + 2 + FW + 2, fieldY, BW, 20).build());
        return field;
    }

    private EditBox buildSizeField(int x, int y, int defaultVal) {
        EditBox field = new EditBox(font, x, y, SF_W, 20, Component.empty());
        field.setMaxLength(4);
        field.setValue(String.valueOf(defaultVal));
        addRenderableWidget(field);
        return field;
    }

    // -------------------------------------------------------------------------
    // Logic

    private void nudge(int axis, int delta) {
        EditBox f = axis == 0 ? xField : axis == 1 ? yField : zField;
        try { f.setValue(String.valueOf(Integer.parseInt(f.getValue().trim()) + delta)); }
        catch (NumberFormatException ignored) {}
        sendBlocks(true);
    }

    private void sendBlocks(boolean preview) {
        if (generating) return;

        String prompt = promptField.getValue().trim();
        if (prompt.isEmpty()) { statusMessage = "Error: prompt cannot be empty"; return; }

        int tx, ty, tz;
        try {
            tx = Integer.parseInt(xField.getValue().trim());
            ty = Integer.parseInt(yField.getValue().trim());
            tz = Integer.parseInt(zField.getValue().trim());
        } catch (NumberFormatException e) { statusMessage = "Error: X/Y/Z must be integers"; return; }

        int sw, sh, sd;
        try {
            sw = Math.max(1, Math.min(96, Integer.parseInt(wField.getValue().trim())));
            sh = Math.max(1, Math.min(96, Integer.parseInt(hField.getValue().trim())));
            sd = Math.max(1, Math.min(96, Integer.parseInt(dField.getValue().trim())));
        } catch (NumberFormatException e) { statusMessage = "Error: W/H/D must be integers"; return; }

        int[] maxSize = {sw, sh, sd};

        if (prompt.equals(cachedPrompt) && !cachedRelativeBlocks.isEmpty()) {
            applyGeneratedBlocks(cachedRelativeBlocks, tx, ty, tz, preview);
        } else {
            requestBlocks(prompt, maxSize, tx, ty, tz, preview);
        }
    }

    private void requestBlocks(String prompt, int[] maxSize, int tx, int ty, int tz, boolean preview) {
        generating = true;
        setButtonsEnabled(false);
        statusMessage = "Generating...";
        placed = 0; total = 0;

        BuildState.INSTANCE.startBackend();

        BackendClient.generateBlocks(prompt, maxSize, update ->
                BuildState.INSTANCE.updateBackend(update.stage(), update.progress())
        ).whenComplete((blocks, error) -> {
            Minecraft mc = Minecraft.getInstance();
            mc.execute(() -> {
                if (error != null) {
                    String msg = formatError(error);
                    BuildState.INSTANCE.setError(msg);
                    onCallbackScreen(s -> { s.generating = false; s.setButtonsEnabled(true); s.statusMessage = msg; });
                    return;
                }
                if (blocks == null || blocks.isEmpty()) {
                    String msg = "Backend returned no blocks";
                    BuildState.INSTANCE.setError(msg);
                    onCallbackScreen(s -> { s.generating = false; s.setButtonsEnabled(true); s.statusMessage = msg; });
                    return;
                }
                cachedPrompt = prompt;
                cachedRelativeBlocks = List.copyOf(blocks);
                onCallbackScreen(s -> { s.cachedPrompt = prompt; s.cachedRelativeBlocks = cachedRelativeBlocks; });
                applyGeneratedBlocks(cachedRelativeBlocks, tx, ty, tz, preview);
            });
        });
    }

    private static void onCallbackScreen(java.util.function.Consumer<ArchitectScreen> fn) {
        Minecraft mc = Minecraft.getInstance();
        if (mc.screen instanceof ArchitectScreen s) fn.accept(s);
    }

    private void applyGeneratedBlocks(List<BuildBlockEntry> relativeBlocks, int tx, int ty, int tz, boolean preview) {
        List<BuildBlockEntry> absoluteBlocks = translateBlocks(relativeBlocks, tx, ty, tz);
        if (preview) {
            BlockPos anchor = minPos(absoluteBlocks);
            GhostPreview.setShape(absoluteBlocks);
            GhostPreview.setOrigin(anchor);
            generating    = false;
            setButtonsEnabled(true);
            statusMessage = "Preview ready — close screen to drag";
            BuildState.INSTANCE.clear();
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
        total  = blocks.size();
        BuildState.INSTANCE.startPlacement(total);
        ClientPlayNetworking.send(new BuildBlocksPayload(blocks, false));
    }

    void setButtonsEnabled(boolean enabled) {
        previewButton.active = enabled;
        placeButton.active   = enabled;
    }

    // -------------------------------------------------------------------------
    // Progress (called from ExampleModClient packet handler)

    public void onProgress(int placedNow, int totalNow, boolean done) {
        placed = placedNow;
        total  = totalNow;
        BuildState.INSTANCE.updatePlacement(placedNow, totalNow, done);
        if (done) {
            generating    = false;
            statusMessage = "Done! Placed " + totalNow + " blocks.";
            setButtonsEnabled(true);
        } else {
            statusMessage = "Placing... " + placedNow + "/" + totalNow;
        }
    }

    // -------------------------------------------------------------------------
    // Helpers

    private static List<BuildBlockEntry> translateBlocks(List<BuildBlockEntry> blocks, int ox, int oy, int oz) {
        List<BuildBlockEntry> out = new ArrayList<>(blocks.size());
        for (BuildBlockEntry b : blocks)
            out.add(new BuildBlockEntry(ox + b.x(), oy + b.y(), oz + b.z(), b.block()));
        return out;
    }

    private static BlockPos minPos(List<BuildBlockEntry> blocks) {
        BuildBlockEntry min = Collections.min(blocks,
                Comparator.comparingInt(BuildBlockEntry::x)
                        .thenComparingInt(BuildBlockEntry::y)
                        .thenComparingInt(BuildBlockEntry::z));
        return new BlockPos(min.x(), min.y(), min.z());
    }

    private static String formatError(Throwable error) {
        Throwable current = error;
        while (current.getCause() != null) current = current.getCause();
        String msg = current.getMessage();
        return (msg == null || msg.isBlank()) ? "Backend request failed" : msg;
    }

    // -------------------------------------------------------------------------
    // Rendering

    @Override
    public void extractRenderState(GuiGraphicsExtractor g, int mx, int my, float delta) {
        int px = (width  - PANEL_W) / 2;
        int py = (height - PANEL_H) / 2;

        g.fill(px, py, px + PANEL_W, py + PANEL_H, BG);
        border(g, px, py, PANEL_W, PANEL_H, ACCENT);
        g.fill(px, py, px + PANEL_W, py + 18, ACCENT);
        g.centeredText(font, title, width / 2, py + 5, 0xFFFFFF);

        g.text(font, "Describe your structure:", px + 10, py + 26, 0xCCCCCC);

        // Origin axis labels
        for (int i = 0; i < 3; i++) {
            String label = i == 0 ? "X" : i == 1 ? "Y" : "Z";
            int cx = px + 10 + i * (GW + GAP) + GW / 2;
            g.centeredText(font, label, cx, py + 62, 0xAAAAAA);
        }

        // Size labels
        String[] sizeLabels = {"W", "H", "D"};
        for (int i = 0; i < 3; i++) {
            int cx = px + 10 + i * (SF_W + SF_GAP) + SF_W / 2;
            g.centeredText(font, sizeLabels[i], cx, py + 97, 0xAAAAAA);
        }

        super.extractRenderState(g, mx, my, delta);

        // Progress bar + stage label — always shown while active
        if (generating || BuildState.INSTANCE.isActive()) {
            BuildState state  = BuildState.INSTANCE;
            float      prog   = state.getOverallProgress();
            String     stage  = generating ? state.getStatusMessage() : statusMessage;

            int bx = px + 10, bw = PANEL_W - 20;
            int barY = py + 170;

            // Dark track
            g.fill(bx, barY, bx + bw, barY + 12, 0xFF222222);
            // Filled portion
            int filled = (int) (prog * bw);
            if (filled > 0)
                g.fill(bx, barY, bx + filled, barY + 12, ACCENT);
            // Leading edge highlight
            if (filled > 0 && filled < bw)
                g.fill(bx + filled, barY, bx + filled + 1, barY + 12, 0xFFFFFFFF);
            // Stage text centered on the bar
            if (!stage.isEmpty())
                g.centeredText(font, stage, width / 2, barY + 2, 0xFFFFFF);
        } else if (!statusMessage.isEmpty()) {
            g.centeredText(font, statusMessage, width / 2, py + 173, 0xAAAAAA);
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
