package com.example.client;

import com.example.network.BuildBlockEntry;
import com.example.network.BuildBlocksPayload;
import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import net.fabricmc.fabric.api.client.networking.v1.ClientPlayNetworking;
import net.minecraft.client.Minecraft;
import net.minecraft.client.gui.GuiGraphics;
import net.minecraft.client.gui.components.Button;
import net.minecraft.client.gui.components.EditBox;
import net.minecraft.client.gui.screens.Screen;
import net.minecraft.network.chat.Component;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.ArrayList;
import java.util.List;

public class ArchitectScreen extends Screen {

    // ── Change this to match your backend URL ──────────────────────────────
    static final String API_URL = "http://localhost:8000/generate";
    // ───────────────────────────────────────────────────────────────────────

    private static final int PANEL_W = 340;
    private static final int PANEL_H = 155;
    private static final int ACCENT  = 0xFF5566FF;
    private static final int BG      = 0xDD000000;

    private EditBox promptField;
    private Button  generateButton;

    private String  statusMessage = "";
    private int     placed        = 0;
    private int     total         = 0;
    private boolean generating    = false;

    public ArchitectScreen() {
        super(Component.literal("AI Architect"));
    }

    // -------------------------------------------------------------------------
    // Layout
    // -------------------------------------------------------------------------

    @Override
    protected void init() {
        int px = (width  - PANEL_W) / 2;
        int py = (height - PANEL_H) / 2;

        promptField = new EditBox(font, px + 10, py + 36, PANEL_W - 20, 20,
                Component.literal("prompt"));
        promptField.setMaxLength(256);
        promptField.setHint(Component.literal("e.g. medieval castle, cosy wood cabin..."));
        addRenderableWidget(promptField);

        generateButton = Button.builder(Component.literal("Generate"), btn -> submit())
                .bounds(px + PANEL_W / 2 - 60, py + 72, 120, 20)
                .build();
        addRenderableWidget(generateButton);

        setInitialFocus(promptField);
    }

    // -------------------------------------------------------------------------
    // HTTP call + JSON parse (runs on a virtual thread)
    // -------------------------------------------------------------------------

    private void submit() {
        String prompt = promptField.getValue().trim();
        if (prompt.isEmpty() || generating) return;

        generating    = true;
        statusMessage = "Calling AI backend...";
        generateButton.active = false;

        Thread.ofVirtual().name("architect-api").start(() -> {
            try {
                String body   = postPrompt(prompt);
                List<BuildBlockEntry> blocks = parseBlocks(body);

                Minecraft.getInstance().execute(() -> {
                    if (blocks.isEmpty()) { onError("Backend returned no blocks."); return; }
                    total         = blocks.size();
                    placed        = 0;
                    statusMessage = "Sending " + total + " blocks to server...";
                    ClientPlayNetworking.send(new BuildBlocksPayload(blocks));
                });
            } catch (Exception ex) {
                Minecraft.getInstance().execute(() -> onError(ex.getMessage()));
            }
        });
    }

    /** POST {"prompt":"..."} to the backend, return raw response body. */
    private static String postPrompt(String prompt) throws Exception {
        JsonObject requestBody = new JsonObject();
        requestBody.addProperty("prompt", prompt);

        HttpRequest req = HttpRequest.newBuilder()
                .uri(URI.create(API_URL))
                .header("Content-Type", "application/json")
                .POST(HttpRequest.BodyPublishers.ofString(requestBody.toString()))
                .timeout(Duration.ofSeconds(60))
                .build();

        HttpResponse<String> resp = HttpClient.newHttpClient()
                .send(req, HttpResponse.BodyHandlers.ofString());

        if (resp.statusCode() != 200)
            throw new RuntimeException("HTTP " + resp.statusCode() + " from backend");

        return resp.body();
    }

    /**
     * Accepts either:
     *   [{"x":0,"y":0,"z":0,"block":"minecraft:stone_bricks"}, ...]
     *   {"blocks":[...]}
     */
    private static List<BuildBlockEntry> parseBlocks(String json) {
        JsonElement root = JsonParser.parseString(json);
        JsonArray arr = root.isJsonArray()
                ? root.getAsJsonArray()
                : root.getAsJsonObject().getAsJsonArray("blocks");

        List<BuildBlockEntry> list = new ArrayList<>(arr.size());
        for (JsonElement el : arr) {
            JsonObject o = el.getAsJsonObject();
            list.add(new BuildBlockEntry(
                    o.get("x").getAsInt(),
                    o.get("y").getAsInt(),
                    o.get("z").getAsInt(),
                    o.get("block").getAsString()
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
        statusMessage = "Error: " + (msg != null ? msg : "unknown");
        generateButton.active = true;
    }

    // -------------------------------------------------------------------------
    // Rendering
    // -------------------------------------------------------------------------

    @Override
    public void render(GuiGraphics g, int mx, int my, float delta) {
        renderBackground(g, mx, my, delta);

        int px = (width  - PANEL_W) / 2;
        int py = (height - PANEL_H) / 2;

        // Panel background + border
        g.fill(px, py, px + PANEL_W, py + PANEL_H, BG);
        border(g, px, py, PANEL_W, PANEL_H, ACCENT);

        // Title bar
        g.fill(px, py, px + PANEL_W, py + 18, ACCENT);
        g.drawCenteredString(font, title, width / 2, py + 5, 0xFFFFFF);

        // Label above text field
        g.drawString(font, "Describe your structure:", px + 10, py + 26, 0xCCCCCC);

        super.render(g, mx, my, delta); // draws EditBox + Button

        // Status text
        if (!statusMessage.isEmpty())
            g.drawCenteredString(font, statusMessage, width / 2, py + 103, 0xAAAAAA);

        // Progress bar
        if (total > 0) {
            int bx = px + 10, by = py + 118, bw = PANEL_W - 20;
            int filled = (int) ((float) placed / total * bw);
            g.fill(bx,          by, bx + bw,       by + 6, 0xFF222222);
            g.fill(bx,          by, bx + filled,   by + 6, ACCENT);
            if (filled > 0 && filled < bw)
                g.fill(bx + filled, by, bx + filled + 1, by + 6, 0xFFFFFFFF);
        }
    }

    private static void border(GuiGraphics g, int x, int y, int w, int h, int c) {
        g.fill(x,         y,         x + w, y + 1,     c);
        g.fill(x,         y + h - 1, x + w, y + h,     c);
        g.fill(x,         y,         x + 1, y + h,     c);
        g.fill(x + w - 1, y,         x + w, y + h,     c);
    }

    // -------------------------------------------------------------------------
    // Input
    // -------------------------------------------------------------------------

    @Override
    public boolean keyPressed(int key, int scan, int mods) {
        if ((key == 257 || key == 335) && !generating) { submit(); return true; } // Enter
        return super.keyPressed(key, scan, mods); // ESC handled by Screen base class
    }

    @Override
    public boolean isPauseScreen() { return false; }
}
