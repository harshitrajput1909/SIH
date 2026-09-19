package com.trustvision.dataset.service;

import com.trustvision.dataset.config.AppProperties;
import org.springframework.stereotype.Service;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.DigestInputStream;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.HexFormat;
import java.util.UUID;

/** Filesystem artefact store (swap for MinIO/S3 in scaled deployments). */
@Service
public class StorageService {

    public record StoredFile(String absolutePath, long sizeBytes, String sha256) {
    }

    private final Path root;

    public StorageService(AppProperties properties) {
        this.root = properties.storage().root().toAbsolutePath().normalize();
    }

    /** Streams the upload to disk while computing its SHA-256 (single pass). */
    public StoredFile storeDatasetArtefact(UUID datasetId, MultipartFile file) throws IOException {
        Path dir = root.resolve("datasets").resolve(datasetId.toString());
        Files.createDirectories(dir);
        Path target = dir.resolve("dataset.zip");
        MessageDigest digest = newSha256();
        long size;
        try (InputStream in = file.getInputStream();
             DigestInputStream digesting = new DigestInputStream(in, digest);
             OutputStream out = Files.newOutputStream(target)) {
            size = digesting.transferTo(out);
        }
        return new StoredFile(target.toString(), size, HexFormat.of().formatHex(digest.digest()));
    }

    public Path storeReport(UUID reportId, byte[] bytes) throws IOException {
        Path dir = root.resolve("reports").resolve(reportId.toString());
        Files.createDirectories(dir);
        Path target = dir.resolve("report.json");
        Files.write(target, bytes);
        return target.toAbsolutePath();
    }

    /** Streams any inference artifact (image / model / output) while hashing it. */
    public StoredFile storeInferenceArtifact(UUID requestId, String slot, MultipartFile file) throws IOException {
        Path dir = root.resolve("inference").resolve(requestId.toString());
        Files.createDirectories(dir);
        String original = file.getOriginalFilename();
        String extension = original != null && original.contains(".")
                ? original.substring(original.lastIndexOf('.'))
                : ".bin";
        Path target = dir.resolve(slot + extension).toAbsolutePath();
        MessageDigest digest = newSha256();
        long size;
        try (InputStream in = file.getInputStream();
             DigestInputStream digesting = new DigestInputStream(in, digest);
             OutputStream out = Files.newOutputStream(target)) {
            size = digesting.transferTo(out);
        }
        return new StoredFile(target.toString(), size, HexFormat.of().formatHex(digest.digest()));
    }

    private static MessageDigest newSha256() {
        try {
            return MessageDigest.getInstance("SHA-256");
        } catch (NoSuchAlgorithmException e) {
            throw new IllegalStateException("SHA-256 unavailable", e);
        }
    }
}
