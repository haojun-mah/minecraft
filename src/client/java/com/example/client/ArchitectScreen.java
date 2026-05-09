package com.example.client;

import com.example.network.BuildBlockEntry;
import com.example.network.BuildBlocksPayload;
import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import net.fabricmc.fabric.api.client.networking.v1.ClientPlayNetworking;
import net.minecraft.client.MinecraftClient;
import net.minecraft.client.gui.DrawContext;
import net.minecraft.client.gui.screen.Screen;
import net.minecraft.client.gui.widget.ButtonWidget;
import net.minecraft.client.gui.widget.TextFieldWidget;
import net.minecraft.text.Text;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.ArrayList;
import java.util.List;

public class ArchitectScreen extends Screen {

    // ── Change this to match your backend ──────────────────────────────────
    private static final String API_URL = "http://localhost:8000/generate";
    // ───────────────────────────────────────────────────────────────────────

    private static final int PANEL_W = 340;
    private static final int PANEL_H = 155;
    private static final int ACCENT  = 0xFF5566FF;
    private static final int BG      = 0xDD000000;

    private TextFieldWidget promptField;
    private ButtonWidget    generateButton;

    private String  statusMessage = "";
    private int     placed        = 0;
    private int     total         = 0;
    private boolean generating    = false;

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
    // API call (runs on a virtual thread, never blocks the game thread)
    // -------------------------------------------------------------------------

    private void submit() {
        String prompt = promptField.getText().trim();
        if (prompt.isEmpty() || generating) return;

        generating    = true;
        statusMessage = "Calling AI backend...";
        generateButton.active = false;

        Thread.ofVirtual().name("architect-api").start(() -> {
            try {
                String responseBody = postPrompt(prompt);
                List<BuildBlockEntry> blocks = parseBlocks(responseBody);

                MinecraftClient.getInstance().execute(() -> {
                    if (blocks.isEmpty()) {
                        onError("Backend returned no blocks.");
                        return;
                    }
                    total         = blocks.size();
                    placed        = 0;
                    statusMessage = "Sending " + total + " blocks to server...";
                    ClientPlayNetworking.send(new BuildBlocksPayload(blocks));
                });

            } catch (Exception ex) {
                MinecraftClient.getInstance().execute(() -> onError(ex.getMessage()));
            }
        });
    }

    // POST {"prompt": "..."} and return the raw response body.
    private static String postPrompt(String prompt) throws Exception {
        JsonObject body = new JsonObject();
        body.addProperty("prompt", prompt);

        HttpRequest request = HttpRequest.newBuilder()
                .uri(URI.create(API_URL))
                .header("Content-Type", "application/json")
                .POST(HttpRequest.BodyPublishers.ofString(body.toString()))
                .timeout(Duration.ofSeconds(60))
                .build();

        HttpResponse<String> response = HttpClient.newHttpClient()
                .send(request, HttpResponse.BodyHandlers.ofString());

        if (response.statusCode() != 200) {
            throw new RuntimeException("HTTP " + response.statusCode() + " from backend");
        }
        return response.body();
    }

    /**
     * Parses the backend JSON response into a list of block entries.
     *
     * Accepts two shapes:
     *   Array root : [{"x":0,"y":0,"z":0,"block":"minecraft:stone_bricks"}, ...]
     *   Object root: {"blocks": [...]}
     */
    private static List<BuildBlockEntry> parseBlocks(String json) {
        JsonElement root = JsonParser.parseString(json);

        JsonArray arr;
        if (root.isJsonArray()) {
            arr = root.getAsJsonArray();
        } else {
            arr = root.getAsJsonObject().getAsJsonArray("blocks");
        }

        List<BuildBlockEntry> list = new ArrayList<>(arr.size());
        for (JsonElement el : arr) {
            JsonObject obj = el.getAsJsonObject();
            list.add(new BuildBlockEntry(
                    obj.get("x").getAsInt(),
                    obj.get("y").getAsInt(),
                    obj.get("z").getAsInt(),
                    obj.get("block").getAsString()
            ));
        }
        return list;
    }

    // -------------------------------------------------------------------------
    // Progress updates from the server
    // -------------------------------------------------------------------------

    /** Called by ExampleModClient when a BuildProgressPayload arrives. */
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

    private void onError(String msg) {
        generating    = false;
        statusMessage = "Error: " + msg;
        generateButton.active = true;
    }

    // -------------------------------------------------------------------------
    // Rendering
    // -------------------------------------------------------------------------

    @Override
    public void render(DrawContext ctx, int mx, int my, float delta) {
        renderBackground(ctx, mx, my, delta);

        int px = (width  - PANEL_W) / 2;
        int py = (height - PANEL_H) / 2;

        ctx.fill(px, py, px + PANEL_W, py + PANEL_H, BG);
        drawBorder(ctx, px, py, PANEL_W, PANEL_H, ACCENT);

        // Title bar
        ctx.fill(px, py, px + PANEL_W, py + 18, ACCENT);
        ctx.drawCenteredTextWithShadow(textRenderer, title, width / 2, py + 5, 0xFFFFFF);

        ctx.drawTextWithShadow(textRenderer,
                Text.literal("Describe your structure:"),
                px + 10, py + 26, 0xCCCCCC);

        super.render(ctx, mx, my, delta); // widgets

        if (!statusMessage.isEmpty()) {
            ctx.drawCenteredTextWithShadow(textRenderer,
                    Text.literal(statusMessage), width / 2, py + 103, 0xAAAAAA);
        }

        if (total > 0) {
            int barX = px + 10;
            int barY = py + 118;
            int barW = PANEL_W - 20;
            int filled = (int) ((float) placed / total * barW);
            ctx.fill(barX,          barY, barX + barW,       barY + 6, 0xFF222222);
            ctx.fill(barX,          barY, barX + filled,     barY + 6, ACCENT);
            if (filled > 0 && filled < barW)
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
        if (key == 256) { close(); return true; }
        if ((key == 257 || key == 335) && !generating) { submit(); return true; }
        return super.keyPressed(key, scan, mods);
    }

    @Override
    public boolean shouldPause() { return false; }
}
