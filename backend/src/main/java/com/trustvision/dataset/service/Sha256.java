package com.trustvision.dataset.service;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.HexFormat;

/** SHA-256 helper (Spring's DigestUtils only ships MD5). */
public final class Sha256 {

    private Sha256() {
    }

    public static String hex(byte[] data) {
        return HexFormat.of().formatHex(newDigest().digest(data));
    }

    public static String hex(String text) {
        return hex(text.getBytes(StandardCharsets.UTF_8));
    }

    private static MessageDigest newDigest() {
        try {
            return MessageDigest.getInstance("SHA-256");
        } catch (NoSuchAlgorithmException e) {
            throw new IllegalStateException("SHA-256 unavailable", e);
        }
    }
}
