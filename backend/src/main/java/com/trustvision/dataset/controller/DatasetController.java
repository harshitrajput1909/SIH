package com.trustvision.dataset.controller;

import com.trustvision.dataset.dto.request.AnalyzeRequest;
import com.trustvision.dataset.dto.response.DatasetAnalysisResponse;
import com.trustvision.dataset.dto.response.DatasetDetailResponse;
import com.trustvision.dataset.dto.response.DatasetResponse;
import com.trustvision.dataset.dto.response.EvidenceResponse;
import com.trustvision.dataset.dto.response.ReportResponse;
import com.trustvision.dataset.service.DatasetService;
import com.trustvision.dataset.service.ReportService;
import com.trustvision.dataset.validation.DatasetFormat;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;

import java.util.List;

@RestController
@RequestMapping("/dataset")
@Validated
public class DatasetController {

    private final DatasetService datasetService;
    private final ReportService reportService;

    public DatasetController(DatasetService datasetService, ReportService reportService) {
        this.datasetService = datasetService;
        this.reportService = reportService;
    }

    @PostMapping(value = "/upload", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    @ResponseStatus(HttpStatus.CREATED)
    public DatasetResponse upload(
            @RequestParam("file") MultipartFile file,
            @RequestParam @NotBlank(message = "name is required") @Size(max = 120, message = "name must be at most 120 characters") String name,
            @RequestParam(required = false) @Size(max = 60, message = "codename must be at most 60 characters") String codename,
            @RequestParam @DatasetFormat String format,
            @RequestParam(required = false) @Size(max = 40) String classification,
            @RequestParam(required = false) @Size(max = 2000) String notes
    ) {
        return datasetService.upload(file, name, codename, format, classification, notes);
    }

    @PostMapping("/analyze")
    public DatasetAnalysisResponse analyze(@Valid @RequestBody AnalyzeRequest request) {
        return datasetService.analyze(request);
    }

    @GetMapping("/{id}")
    public DatasetDetailResponse get(@PathVariable @NotNull java.util.UUID id) {
        return datasetService.get(id);
    }

    @GetMapping("/report/{id}")
    public ReportResponse report(@PathVariable @NotNull java.util.UUID id) {
        return reportService.getOrGenerate(id);
    }

    @GetMapping("/evidence/{id}")
    public List<EvidenceResponse> evidence(
            @PathVariable @NotNull java.util.UUID id) {
        return datasetService.evidence(id);
    }
}
