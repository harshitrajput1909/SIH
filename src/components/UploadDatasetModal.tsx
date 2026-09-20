import { useEffect, useRef, useState } from 'react';
import { AlertCircle, CheckCircle2, CloudUpload, Loader2, X } from 'lucide-react';
import { Button } from './ui/Button';

const ACCEPTED_EXTENSIONS = ['.zip'];
const MAX_FILE_SIZE_BYTES = 200 * 1024 * 1024;

function formatBytes(bytes: number) {
  if (bytes === 0) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB'];
  const unitIndex = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  const value = bytes / 1024 ** unitIndex;
  return `${value.toFixed(value >= 10 || unitIndex === 0 ? 0 : 1)} ${units[unitIndex]}`;
}

function getSanitizedName(fileName: string) {
  return fileName
    .replace(/\.[^/.]+$/, '')
    .replace(/[^a-zA-Z0-9 _-]/g, '')
    .trim()
    .replace(/\s+/g, ' ')
    .slice(0, 80) || 'dataset';
}

export function UploadDatasetModal({
  open,
  uploading,
  processing,
  error,
  onClose,
  onUpload,
}: {
  open: boolean;
  uploading: boolean;
  processing: boolean;
  error: string | null;
  onClose: () => void;
  onUpload: (file: File, datasetName: string) => Promise<void> | void;
}) {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [datasetName, setDatasetName] = useState('');
  const [validationError, setValidationError] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);

  useEffect(() => {
    if (!open) {
      setSelectedFile(null);
      setDatasetName('');
      setValidationError(null);
      setDragging(false);
    }
  }, [open]);

  const validateFile = (file: File | null) => {
    if (!file) {
      return 'Please select a dataset file.';
    }

    if (file.size <= 0) {
      return 'The selected file is empty.';
    }

    if (file.size > MAX_FILE_SIZE_BYTES) {
      return 'File exceeds the 200 MB upload limit.';
    }

    const extension = `.${file.name.split('.').pop()?.toLowerCase() ?? ''}`;
    if (!ACCEPTED_EXTENSIONS.includes(extension)) {
      return 'Unsupported file type. Please upload a ZIP archive containing the dataset.';
    }

    return null;
  };

  const handleFileSelection = (file: File | null) => {
    const message = validateFile(file);
    if (message) {
      setValidationError(message);
      setSelectedFile(null);
      return;
    }

    setValidationError(null);
    setSelectedFile(file);
    if (!datasetName && file) {
      setDatasetName(getSanitizedName(file.name));
    }
  };

  const handleSubmit = async () => {
    if (!selectedFile) {
      setValidationError('Please choose a dataset file before uploading.');
      return;
    }

    const message = validateFile(selectedFile);
    if (message) {
      setValidationError(message);
      return;
    }

    const nextName = datasetName.trim() || getSanitizedName(selectedFile.name);
    await onUpload(selectedFile, nextName);
  };

  if (!open) return null;

  const isBusy = uploading || processing;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/55 p-4">
      <div className="w-full max-w-xl rounded-2xl border border-slate-200 bg-white shadow-2xl">
        <div className="flex items-center justify-between border-b border-slate-200 px-5 py-4">
          <div>
            <p className="text-lg font-semibold text-slate-800">Upload dataset</p>
            <p className="text-xs text-slate-500">Secure dataset import into TRUSTVISION</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close upload modal"
            className="rounded-lg p-2 text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-600"
          >
            <X size={17} />
          </button>
        </div>

        <div className="space-y-5 p-5">
          <div>
            <label htmlFor="dataset-name" className="mb-1.5 block text-sm font-medium text-slate-700">
              Dataset name
            </label>
            <input
              id="dataset-name"
              value={datasetName}
              onChange={(event) => setDatasetName(event.target.value)}
              placeholder="e.g. coco_dataset_v2"
              className="h-11 w-full rounded-lg border border-slate-200 bg-slate-50 px-3 text-sm text-slate-800 placeholder:text-slate-400 focus:border-navy-500 focus:bg-white focus:outline-none"
            />
          </div>

          <div
            onDragOver={(event) => {
              event.preventDefault();
              setDragging(true);
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={(event) => {
              event.preventDefault();
              setDragging(false);
              handleFileSelection(event.dataTransfer.files?.[0] ?? null);
            }}
            className={`rounded-2xl border border-dashed p-5 text-center transition-colors ${
              dragging ? 'border-navy-500 bg-navy-50' : 'border-slate-300 bg-slate-50'
            }`}
          >
            <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-white text-navy-700 shadow-sm">
              <CloudUpload size={22} />
            </div>
            <p className="mt-4 text-sm font-medium text-slate-700">Drop your dataset here</p>
            <p className="mt-1 text-xs text-slate-500">or browse from your device</p>

            <div className="mt-4 flex justify-center gap-3">
              <Button type="button" variant="secondary" onClick={() => inputRef.current?.click()} disabled={isBusy}>
                Browse Files
              </Button>
            </div>

            <input
              ref={inputRef}
              type="file"
              accept=".zip"
              hidden
              onChange={(event) => handleFileSelection(event.target.files?.[0] ?? null)}
            />
          </div>

          <div className="grid gap-2 text-xs text-slate-500 sm:grid-cols-2">
            <div>Supported format: .zip dataset archive</div>
          </div>

          {selectedFile ? (
            <div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
              <div className="flex items-center justify-between gap-3">
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium text-slate-800">{selectedFile.name}</p>
                  <p className="text-xs text-slate-500">{formatBytes(selectedFile.size)}</p>
                </div>
                <button
                  type="button"
                  onClick={() => {
                    setSelectedFile(null);
                    setValidationError(null);
                    if (inputRef.current) inputRef.current.value = '';
                  }}
                  className="rounded-md border border-slate-200 bg-white px-2 py-1 text-xs text-slate-600 hover:bg-slate-100"
                >
                  Remove
                </button>
              </div>
            </div>
          ) : null}

          {(validationError || error) && (
            <div className="flex items-start gap-2 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
              <AlertCircle size={16} className="mt-0.5 shrink-0" />
              <span>{validationError ?? error}</span>
            </div>
          )}

          {isBusy ? (
            <div className="rounded-xl border border-sky-200 bg-sky-50 p-3">
              <div className="flex items-center gap-2 text-sm font-medium text-sky-800">
                <Loader2 className="h-4 w-4 animate-spin" />
                {processing ? 'Processing dataset…' : 'Uploading dataset…'}
              </div>
              <div className="mt-2 h-2 overflow-hidden rounded-full bg-sky-100">
                <div
                  className="h-full rounded-full bg-sky-600 transition-all duration-500"
                  style={{ width: processing ? '85%' : '55%' }}
                />
              </div>
            </div>
          ) : null}

          {(!validationError && !error && selectedFile && !isBusy) ? (
            <div className="flex items-center gap-2 rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-700">
              <CheckCircle2 size={16} className="shrink-0" />
              <span>Ready to upload</span>
            </div>
          ) : null}

          <div className="flex justify-end gap-3 pt-2">
            <Button type="button" variant="secondary" onClick={onClose} disabled={isBusy}>
              Cancel
            </Button>
            <Button type="button" onClick={handleSubmit} disabled={!selectedFile || isBusy}>
              {uploading ? 'Uploading...' : processing ? 'Processing...' : 'Upload Dataset'}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
