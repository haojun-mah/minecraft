package com.example.client;

import com.example.network.BuildRequestPayload;
import net.fabricmc.fabric.api.client.networking.v1.ClientPlayNetworking;
import net.minecraft.client.gui.DrawContext;
import net.minecraft.client.gui.screen.Screen;
import net.minecraft.client.gui.widget.ButtonWidget;
import net.minecraft.client.gui.widget.TextFieldWidget;
import net.minecraft.text.Text;

public class ArchitectScreen extends Screen {

    private static final int PANEL_W = 340;
    private static final int PANEL_H = 150;
    private static final int ACCENT  = 0xFF5566FF;
    private static final int BG      = 0xDD000000;

    private TextFieldWidget promptField;
    private ButtonWidget generateButton;

    private String statusMessage = "";
    private int placed = 0;
    private int total  = 0;
    private boolean generating = false;

    public ArchitectScreen() {
        super(Text.literal("AI Architect"));
    }

    // -------------------------------------------------------------------------
    // Layout
    // -------------------------------------------------------------------------

    @Override
    protected void init() {
        int px = (width  - PANEL_W) / 2;
        int py = (height - PANEL_H) / 2;

        promptField = new TextFieldWidget(
                textRenderer,
                px + 10, py + 36,
                PANEL_W - 20, 20,
                Text.literal("prompt")
        );
        promptField.setMaxLength(256);
        promptField.setPlaceholder(Text.literal("e.g. medieval castle, cosy wood cabin..."));
        addDrawableChild(promptField);

        generateButton = ButtonWidget.builder(Text.literal("Generate"), btn -> submit())
                .dimensions(px + PANEL_W / 2 - 60, py + 72, 120, 20)
                .build();
        addDrawableChild(generateButton);

        setInitialFocus(promptField);
    }

    // -------------------------------------------------------------------------
    // Logic
    // -------------------------------------------------------------------------

    private void submit() {
        String prompt = promptField.getText().trim();
        if (prompt.isEmpty() || generating) return;

        generating = true;
        placed = 0;
        total  = 0;
        statusMessage = "Sending to AI...";
        generateButton.active = false;

        ClientPlayNetworking.send(new BuildRequestPayload(prompt));
    }

    /** Called from ExampleModClient when a BuildProgressPayload arrives. */
    public void onProgress(int placed, int total, boolean done) {
        this.placed = placed;
        this.total  = total;

        if (done) {
            generating    = false;
            statusMessage = "Done! Placed " + total + " blocks.";
            generateButton.active = true;
        } else {
            statusMessage = "Building... " + placed + "/" + total;
        }
    }

    // -------------------------------------------------------------------------
    // Rendering
    // -------------------------------------------------------------------------

    @Override
    public void render(DrawContext ctx, int mx, int my, float delta) {
        renderBackground(ctx, mx, my, delta);

        int px = (width  - PANEL_W) / 2;
        int py = (height - PANEL_H) / 2;

        // Panel background
        ctx.fill(px, py, px + PANEL_W, py + PANEL_H, BG);
        drawBorder(ctx, px, py, PANEL_W, PANEL_H, ACCENT);

        // Title bar
        ctx.fill(px, py, px + PANEL_W, py + 18, ACCENT);
        ctx.drawCenteredTextWithShadow(textRenderer, title, width / 2, py + 5, 0xFFFFFF);

        // Label
        ctx.drawTextWithShadow(textRenderer,
                Text.literal("Describe your structure:"),
                px + 10, py + 26, 0xCCCCCC);

        // Widgets (text field + button)
        super.render(ctx, mx, my, delta);

        // Status text
        if (!statusMessage.isEmpty()) {
            ctx.drawCenteredTextWithShadow(textRenderer,
                    Text.literal(statusMessage), width / 2, py + 103, 0xAAAAAA);
        }

        // Progress bar (shown while building)
        if (generating && total > 0) {
            int barX = px + 10;
            int barY = py + 118;
            int barW = PANEL_W - 20;
            int filled = (int) ((float) placed / total * barW);
            ctx.fill(barX,          barY, barX + barW,    barY + 6, 0xFF222222);
            ctx.fill(barX,          barY, barX + filled,  barY + 6, ACCENT);
            ctx.fill(barX + filled, barY, barX + filled + 1, barY + 6, 0xFFFFFFFF);
        }
    }

    private static void drawBorder(DrawContext ctx, int x, int y, int w, int h, int color) {
        ctx.fill(x,         y,         x + w,     y + 1,     color);
        ctx.fill(x,         y + h - 1, x + w,     y + h,     color);
        ctx.fill(x,         y,         x + 1,     y + h,     color);
        ctx.fill(x + w - 1, y,         x + w,     y + h,     color);
    }

    // -------------------------------------------------------------------------
    // Input
    // -------------------------------------------------------------------------

    @Override
    public boolean keyPressed(int key, int scan, int mods) {
        if (key == 256) { close(); return true; }                       // ESC
        if ((key == 257 || key == 335) && !generating) { submit(); return true; } // Enter
        return super.keyPressed(key, scan, mods);
    }

    @Override
    public boolean shouldPause() { return false; }
}
