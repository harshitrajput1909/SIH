export async function requestJson<T>(path: string, init?: RequestInit): Promise<T | null> {
  try {
    const response = await fetch(path, {
      cache: 'no-store',
      ...init,
    });

    if (!response.ok) {
      const payload = await response.json().catch(() => null);
      throw new Error(payload?.message || payload?.error || `Request failed for ${path}`);
    }

    return (await response.json()) as T;
  } catch {
    return null;
  }
}

export async function getJson<T>(path: string): Promise<T | null> {
  return requestJson<T>(path, {
    method: 'GET',
  });
}

export async function uploadDataset(formData: FormData) {
  const response = await fetch('/dataset/upload', {
    method: 'POST',
    body: formData,
    headers: {
      Accept: 'application/json',
    },
  });

  const data = await response.json().catch(() => null);

  if (!response.ok) {
    throw new Error(
      data?.message || data?.error || 'Dataset upload failed. Please check the file and try again.',
    );
  }

  return data;
}

export async function analyzeDataset(datasetId: string) {
  const response = await fetch('/dataset/analyze', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'application/json',
    },
    body: JSON.stringify({
      datasetId,
      options: {},
      force: true,
    }),
  });

  const data = await response.json().catch(() => null);

  if (!response.ok) {
    throw new Error(data?.message || data?.error || 'Dataset processing could not be started.');
  }

  return data;
}

export async function getDatasetDetail(datasetId: string) {
  const response = await fetch(`/dataset/${datasetId}`, {
    method: 'GET',
    cache: 'no-store',
  });

  if (!response.ok) {
    return null;
  }

  return (await response.json()) as {
    dataset?: {
      name?: string;
      sizeBytes?: number;
      uploadedAt?: string;
      state?: string;
      imageCount?: number;
    };
  } | null;
}

export async function getModelEngineHealth() {
  return requestJson<{ status?: string; version?: string; service?: string; runtime?: Record<string, string | number> }>(
    '/api/health',
    { method: 'GET' },
  );
}

export async function assessModel(modelPath: string, mode: 'WHITE_BOX' | 'BLACK_BOX' = 'WHITE_BOX') {
  return requestJson<{ job_id?: string; status?: string; poll_url?: string; detail?: string }>(
    '/api/v1/assessments',
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
      },
      body: JSON.stringify({
        model_path: modelPath,
        model_format: 'AUTO',
        mode,
        options: {
          probe_count: 10,
          divergence_threshold: 0.3,
          seed: 20260919,
        },
      }),
    },
  );
}
