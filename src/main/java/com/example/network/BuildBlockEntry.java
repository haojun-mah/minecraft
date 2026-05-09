package com.example.network;

/**
 * One block in the AI-generated structure.
 * x/y/z are relative to the player's feet position when the build was triggered.
 * block is the full Minecraft registry name, e.g. "minecraft:stone_bricks".
 */
public record BuildBlockEntry(int x, int y, int z, String block) {}
