package com.trustvision.dataset.validation;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.trustvision.dataset.domain.DatasetFormat;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

import java.io.IOException;
import java.io.InputStream;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.zip.ZipEntry;
import java.util.zip.ZipFile;

/**
 * Validates the structure of an uploaded dataset archive BEFORE any analysis
 * (or downstream training) is started.
 *
 * COCO  : annotations/ with a valid JSON (images + annotations), images/ present
 * YOLO  : images/, labels/ and data.yaml, valid "class cx cy w h" lines
 *
 * On failure the report carries error type, offending files and a suggested fix.
 */
@Component
public class ZipStructureValidator {

    private static final Logger log = LoggerFactory.getLogger(ZipStructureValidator.class);

    private static final Set<String> IMAGE_EXT = Set.of("jpg", "jpeg", "png", "bmp", "webp", "tif", "tiff");
    private static final Set<String> IGNORED = Set.of("__MACOSX", ".DS_Store", "Thumbs.db");

    private static final int MAX_REPORTED_FILES = 12;
    private static final int MAX_LABEL_LINES_CHECKED = 5_000;
    private static final long MAX_ANNOTATION_BYTES = 512L * 1024 * 1024;

    private final ObjectMapper objectMapper = new ObjectMapper();

    public ValidationReport validate(Path zipPath, DatasetFormat declared) {
        List<ValidationReport.ValidationIssue> errors = new ArrayList<>();
        List<ValidationReport.ValidationIssue> warnings = new ArrayList<>();
        Map<String, Object> stats = new LinkedHashMap<>();

        List<String> entries;
        try (ZipFile zip = new ZipFile(zipPath.toFile())) {
            entries = zip.stream().map(ZipEntry::getName).filter(n -> !n.isBlank()).toList();
        } catch (IOException e) {
            return report(false, declared.name(), "UNKNOWN",
                    List.of(issue("CORRUPT_ARCHIVE", "The archive could not be opened as a ZIP file.",
                            List.of(String.valueOf(zipPath.getFileName())),
                            "Re-create the archive with a standard ZIP tool and upload again.")),
                    List.of(), Map.of());
        }

        // ---- generic checks ------------------------------------------------
        List<String> unsafe = entries.stream()
                .filter(n -> n.contains("..") || n.startsWith("/") || n.matches("^[A-Za-z]:.*"))
                .toList();
        if (!unsafe.isEmpty()) {
            errors.add(issue("UNSAFE_ENTRY", "Archive contains unsafe path entries.",
                    unsafe, "Remove absolute paths and '..' segments from the archive."));
        }

        Set<String> ignoredEntries = new HashSet<>();
        List<String> imageEntries = new ArrayList<>();
        List<String> labelEntries = new ArrayList<>();
        List<String> jsonEntries = new ArrayList<>();
        List<String> yamlEntries = new ArrayList<>();
        List<String> unsupported = new ArrayList<>();

        for (String entry : entries) {
            if (entry.endsWith("/")) {
                continue;
            }
            String[] parts = entry.split("/");
            if (IGNORED.contains(parts[0]) || IGNORED.contains(parts[parts.length - 1])) {
                ignoredEntries.add(entry);
                continue;
            }
            String ext = ext(entry);
            String dir = parts.length > 1 ? parts[parts.length - 2] : "";
            if (IMAGE_EXT.contains(ext)) {
                imageEntries.add(entry);
            } else if ("txt".equals(ext) && (dir.equals("labels") || entry.contains("/labels/"))) {
                labelEntries.add(entry);
            } else if ("txt".equals(ext) && entry.endsWith("classes.txt")) {
                labelEntries.add(entry);
            } else if ("json".equals(ext)) {
                jsonEntries.add(entry);
            } else if ("yaml".equals(ext) || "yml".equals(ext)) {
                yamlEntries.add(entry);
            } else if (!Set.of("md", "csv", "txt").contains(ext)) {
                unsupported.add(entry);
            }
        }

        if (!unsupported.isEmpty()) {
            warnings.add(issue("UNSUPPORTED_EXTENSION",
                    "Files with extensions outside the supported set (images, .txt labels, .json, .yaml) were found and will be ignored.",
                    head(unsupported), "Remove unrelated files from the dataset archive."));
        }

        stats.put("imageCount", imageEntries.size());
        stats.put("labelFiles", labelEntries.size());
        stats.put("annotationFiles", jsonEntries.size());
        stats.put("entries", entries.size());

        if (imageEntries.isEmpty()) {
            errors.add(issue("NO_IMAGES", "The dataset contains no images.",
                    List.of(), "Add images (jpg/jpeg/png/bmp/webp/tif/tiff) under images/."));
            return report(false, declared.name(), detectFormat(labelEntries, jsonEntries, yamlEntries, imageEntries),
                    errors, warnings, stats);
        }

        boolean imagesInImagesDir = imageEntries.stream().anyMatch(n -> n.contains("/images/") || n.startsWith("images/"));
        if (!imagesInImagesDir) {
            errors.add(issue("MISSING_IMAGES_DIR",
                    "Images were found, but not inside an images/ directory.",
                    head(imageEntries), "Move all images into an images/ folder (e.g. images/train/)."));
        }

        // ---- format-specific checks ----------------------------------------
        String detected = detectFormat(labelEntries, jsonEntries, yamlEntries, imageEntries);
        if (declared == DatasetFormat.COCO) {
            validateCoco(zipPath, jsonEntries, imageEntries, errors, warnings, stats);
        } else {
            validateYolo(zipPath, yamlEntries, labelEntries, imageEntries, errors, warnings, stats);
        }

        if (!detected.equals(declared.name()) && !"UNKNOWN".equals(detected)) {
            errors.add(issue("UNSUPPORTED_STRUCTURE",
                    "Archive layout looks like " + detected + " but the upload was declared as " + declared.name() + ".",
                    List.of(), "Either re-package the dataset as " + declared.name()
                            + " or upload again with format=" + detected + "."));
        }

        return report(errors.isEmpty(), declared.name(), detected, errors, warnings, stats);
    }

    // ------------------------------------------------------------------
    // COCO
    // ------------------------------------------------------------------

    private void validateCoco(Path zipPath, List<String> jsonEntries, List<String> imageEntries,
                              List<ValidationReport.ValidationIssue> errors, List<ValidationReport.ValidationIssue> warnings,
                              Map<String, Object> stats) {
        List<String> annotationJsons = jsonEntries.stream()
                .filter(n -> n.contains("/annotations/") || !n.contains("/"))
                .toList();
        if (annotationJsons.isEmpty()) {
            errors.add(issue("MISSING_ANNOTATIONS_DIR",
                    "No COCO annotation JSON found (expected annotations/instances_*.json).",
                    List.of(), "Add a COCO annotation file under annotations/ containing 'images' and 'annotations' arrays."));
            return;
        }

        String annotationEntry = annotationJsons.get(0);
        JsonNode root;
        try (ZipFile zip = new ZipFile(zipPath.toFile())) {
            ZipEntry entry = zip.getEntry(annotationEntry);
            if (entry == null || entry.getSize() > MAX_ANNOTATION_BYTES) {
                errors.add(issue("INVALID_ANNOTATION_JSON", "Annotation file is missing or exceeds 512 MB.",
                        List.of(annotationEntry), "Split the dataset or repair the annotation file."));
                return;
            }
            try (InputStream in = zip.getInputStream(entry)) {
                root = objectMapper.readTree(in);
            }
        } catch (IOException e) {
            errors.add(issue("INVALID_ANNOTATION_JSON", "Annotation file could not be parsed as JSON: " + e.getMessage(),
                    List.of(annotationEntry), "Re-export the annotations from your annotation tool."));
            return;
        }

        if (!root.isObject() || !root.has("images") || !root.path("images").isArray()
                || !root.has("annotations") || !root.path("annotations").isArray()) {
            errors.add(issue("INVALID_ANNOTATION_JSON",
                    "Annotation JSON must be an object with 'images' and 'annotations' arrays.",
                    List.of(annotationEntry), "Use a standard COCO export (instances_train.json layout)."));
            return;
        }

        int imageNodes = root.path("images").size();
        int annotationNodes = root.path("annotations").size();
        int categories = root.path("categories").size();
        stats.put("cocoImages", imageNodes);
        stats.put("cocoAnnotations", annotationNodes);
        stats.put("categories", categories);

        if (annotationNodes == 0) {
            errors.add(issue("EMPTY_ANNOTATIONS",
                    "The 'annotations' array is empty — no labelled samples.",
                    List.of(annotationEntry), "Annotate at least some images before uploading."));
        }
        if (categories == 0) {
            warnings.add(issue("MISSING_CATEGORIES",
                    "The 'categories' array is empty — class names cannot be resolved.",
                    List.of(annotationEntry), "Include the category list in the annotation file."));
        }

        Set<String> imageBasenames = new HashSet<>();
        for (String entry : imageEntries) {
            String[] parts = entry.split("/");
            imageBasenames.add(parts[parts.length - 1]);
        }
        List<String> missingImages = new ArrayList<>();
        for (JsonNode imageNode : root.path("images")) {
            String fileName = imageNode.path("file_name").asText("");
            if (fileName.isEmpty()) {
                continue;
            }
            String base = fileName.contains("/") ? fileName.substring(fileName.lastIndexOf('/') + 1) : fileName;
            if (!imageBasenames.contains(base) && missingImages.size() < MAX_REPORTED_FILES) {
                missingImages.add(fileName);
            }
        }
        if (!missingImages.isEmpty()) {
            errors.add(issue("MISSING_IMAGE_FILES",
                    "Annotation references images that are not in the archive.",
                    missingImages, "Include the referenced image files in images/."));
        }
    }

    // ------------------------------------------------------------------
    // YOLO
    // ------------------------------------------------------------------

    private void validateYolo(Path zipPath, List<String> yamlEntries, List<String> labelEntries,
                              List<String> imageEntries, List<ValidationReport.ValidationIssue> errors,
                              List<ValidationReport.ValidationIssue> warnings, Map<String, Object> stats) {
        boolean hasDataYaml = yamlEntries.stream().anyMatch(n -> n.equals("data.yaml") || n.equals("data.yml")
                || n.endsWith("/data.yaml") || n.endsWith("/data.yml"));
        if (!hasDataYaml) {
            errors.add(issue("MISSING_DATA_YAML",
                    "YOLO datasets require a data.yaml defining the class names.",
                    List.of(), "Add data.yaml at the archive root with 'nc:' and 'names:'."));
        } else if (yamlEntries.stream().noneMatch(n -> n.equals("data.yaml"))) {
            warnings.add(issue("DATA_YAML_NESTED",
                    "data.yaml found in a subdirectory rather than the archive root.",
                    head(yamlEntries), "Move data.yaml to the archive root."));
        }

        List<String> realLabels = labelEntries.stream().filter(n -> !n.endsWith("classes.txt")).toList();
        if (realLabels.isEmpty()) {
            errors.add(issue("MISSING_LABEL_FILES",
                    "No YOLO label files found under labels/.",
                    List.of(), "Generate one .txt per image under labels/ (class cx cy w h per line)."));
            return;
        }
        boolean labelsInDir = realLabels.stream().anyMatch(n -> n.contains("/labels/") || n.startsWith("labels/"));
        if (!labelsInDir) {
            errors.add(issue("MISSING_LABELS_DIR",
                    "Label files were found outside a labels/ directory.",
                    head(realLabels), "Move label files into labels/ (e.g. labels/train/)."));
        }

        Set<String> labelStems = new HashSet<>();
        for (String entry : realLabels) {
            String name = entry.substring(entry.lastIndexOf('/') + 1);
            labelStems.add(name.substring(0, name.length() - 4));
        }
        List<String> unlabeled = new ArrayList<>();
        for (String entry : imageEntries) {
            String name = entry.substring(entry.lastIndexOf('/') + 1);
            int dot = name.lastIndexOf('.');
            String stem = dot > 0 ? name.substring(0, dot) : name;
            if (!labelStems.contains(stem) && unlabeled.size() < MAX_REPORTED_FILES) {
                unlabeled.add(entry);
            }
        }
        if (!unlabeled.isEmpty()) {
            int totalUnlabeled = (int) imageEntries.stream().filter(n -> {
                String name = n.substring(n.lastIndexOf('/') + 1);
                int dot = name.lastIndexOf('.');
                String stem = dot > 0 ? name.substring(0, dot) : name;
                return !labelStems.contains(stem);
            }).count();
            warnings.add(issue("IMAGES_WITHOUT_LABELS",
                    totalUnlabeled + " image(s) have no matching .txt label file.",
                    unlabeled, "Label the images or remove them before training."));
        }

        List<String> invalidLines = new ArrayList<>();
        int checkedLines = 0;
        try (ZipFile zip = new ZipFile(zipPath.toFile())) {
            outer:
            for (String labelEntry : realLabels) {
                ZipEntry entry = zip.getEntry(labelEntry);
                if (entry == null) {
                    continue;
                }
                try (InputStream in = zip.getInputStream(entry)) {
                    List<String> lines = new String(in.readAllBytes(), java.nio.charset.StandardCharsets.UTF_8)
                            .lines().filter(l -> !l.isBlank()).toList();
                    for (String line : lines) {
                        checkedLines++;
                        if (!isValidYoloLine(line) && invalidLines.size() < MAX_REPORTED_FILES) {
                            invalidLines.add(labelEntry + ": " + line.trim());
                        }
                        if (checkedLines >= MAX_LABEL_LINES_CHECKED) {
                            break outer;
                        }
                    }
                }
            }
        } catch (IOException e) {
            errors.add(issue("INVALID_LABEL_FORMAT", "Label files could not be read: " + e.getMessage(),
                    List.of(), "Ensure label files are UTF-8 text."));
            return;
        }
        stats.put("labelLinesChecked", checkedLines);
        if (!invalidLines.isEmpty()) {
            errors.add(issue("INVALID_LABEL_FORMAT",
                    "Label lines must be 'class cx cy w h' with an integer class and four numbers in [0,1].",
                    invalidLines, "Re-export labels from your YOLO tool; check class ids and normalized coordinates."));
        }
    }

    private boolean isValidYoloLine(String line) {
        String[] parts = line.trim().split("\\s+");
        if (parts.length < 5) {
            return false;
        }
        try {
            int classId = Integer.parseInt(parts[0]);
            if (classId < 0) {
                return false;
            }
            for (int i = 1; i <= 4; i++) {
                float value = Float.parseFloat(parts[i]);
                if (value < 0.0f || value > 1.0f) {
                    return false;
                }
            }
            return true;
        } catch (NumberFormatException e) {
            return false;
        }
    }

    // ------------------------------------------------------------------
    // helpers
    // ------------------------------------------------------------------

    private String detectFormat(List<String> labels, List<String> jsons, List<String> yamls, List<String> images) {
        boolean yoloMarkers = labels.stream().anyMatch(n -> n.contains("/labels/") || n.startsWith("labels/"))
                && yamls.stream().anyMatch(n -> n.endsWith("data.yaml") || n.endsWith("data.yml"));
        if (yoloMarkers) {
            return "YOLO";
        }
        boolean cocoMarkers = jsons.stream().anyMatch(n -> n.contains("/annotations/"));
        if (cocoMarkers) {
            return "COCO";
        }
        return images.isEmpty() ? "UNKNOWN" : (labels.isEmpty() && !jsons.isEmpty() ? "COCO" : "UNKNOWN");
    }

    private static String ext(String entry) {
        int dot = entry.lastIndexOf('.');
        return dot > 0 ? entry.substring(dot + 1).toLowerCase() : "";
    }

    private static List<String> head(List<String> files) {
        return files.size() > MAX_REPORTED_FILES ? files.subList(0, MAX_REPORTED_FILES) : files;
    }

    private static ValidationReport.ValidationIssue issue(String type, String message,
                                                          List<String> files, String suggestedFix) {
        return new ValidationReport.ValidationIssue(type, message, files == null ? List.of() : files, suggestedFix);
    }

    private static ValidationReport report(boolean valid, String declared, String detected,
                                           List<ValidationReport.ValidationIssue> errors,
                                           List<ValidationReport.ValidationIssue> warnings,
                                           Map<String, Object> stats) {
        log.info("validation finished: valid={} declared={} detected={} errors={} warnings={}",
                valid, declared, detected, errors.size(), warnings.size());
        return new ValidationReport(valid, declared, detected, errors, warnings,
                stats == null ? new HashMap<>() : stats);
    }
}
