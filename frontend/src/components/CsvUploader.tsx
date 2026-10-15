import React, { useState, useRef } from 'react';
import type { ImportSummary } from '../types';

interface CsvUploaderProps {
  onUpload: (file: File) => Promise<ImportSummary>;
  isUploading: boolean;
}

export const CsvUploader: React.FC<CsvUploaderProps> = ({ onUpload, isUploading }) => {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [lastSummary, setLastSummary] = useState<ImportSummary | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [showErrorDetails, setShowErrorDetails] = useState<boolean>(true);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setSelectedFile(e.target.files[0]);
      setErrorMessage(null);
      setLastSummary(null);
    }
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      setSelectedFile(e.dataTransfer.files[0]);
      setErrorMessage(null);
      setLastSummary(null);
    }
  };

  const handleDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedFile) return;

    setErrorMessage(null);
    try {
      const summary = await onUpload(selectedFile);
      setLastSummary(summary);
      setSelectedFile(null);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    } catch (err: unknown) {
      if (err instanceof Error) {
        setErrorMessage(err.message);
      } else {
        setErrorMessage('Failed to upload statement file.');
      }
    }
  };

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-sm">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
        <div>
          <h2 className="text-base font-semibold text-white">Import Bank Statement</h2>
          <p className="text-xs text-slate-400">
            Upload CSV statement (date, description, amount, type, reference)
          </p>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        <div
          onDrop={handleDrop}
          onDragOver={handleDragOver}
          onClick={() => fileInputRef.current?.click()}
          className="border-2 border-dashed border-slate-700 hover:border-blue-500/50 bg-slate-800/40 hover:bg-slate-800/60 transition rounded-xl p-6 text-center cursor-pointer"
        >
          <input
            ref={fileInputRef}
            type="file"
            accept=".csv"
            onChange={handleFileChange}
            className="hidden"
          />
          <div className="flex flex-col items-center justify-center gap-2">
            <div className="h-10 w-10 rounded-full bg-blue-500/10 text-blue-400 flex items-center justify-center">
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
              </svg>
            </div>
            {selectedFile ? (
              <div>
                <p className="text-sm font-medium text-white">{selectedFile.name}</p>
                <p className="text-xs text-slate-400">
                  {(selectedFile.size / 1024).toFixed(1)} KB — Click or submit to process
                </p>
              </div>
            ) : (
              <div>
                <p className="text-sm font-medium text-slate-300">
                  Click to select CSV or drag and drop
                </p>
                <p className="text-xs text-slate-500">Supports standard bank CSV exports</p>
              </div>
            )}
          </div>
        </div>

        <div className="flex items-center justify-end gap-3">
          {selectedFile && (
            <button
              type="button"
              onClick={() => {
                setSelectedFile(null);
                if (fileInputRef.current) fileInputRef.current.value = '';
              }}
              className="text-xs font-medium text-slate-400 hover:text-white px-3 py-2 transition"
            >
              Clear
            </button>
          )}
          <button
            type="submit"
            disabled={!selectedFile || isUploading}
            className="inline-flex items-center justify-center gap-2 bg-blue-600 hover:bg-blue-500 disabled:bg-slate-800 disabled:text-slate-500 text-white text-xs font-semibold px-4 py-2.5 rounded-lg shadow-sm transition cursor-pointer disabled:cursor-not-allowed"
          >
            {isUploading && (
              <svg className="animate-spin h-3.5 w-3.5 text-white" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"></path>
              </svg>
            )}
            {isUploading ? 'Processing & Matching...' : 'Upload & Reconcile'}
          </button>
        </div>
      </form>

      {errorMessage && (
        <div className="mt-4 p-3.5 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 text-xs flex items-start gap-2.5">
          <svg className="w-4 h-4 shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <div className="flex-1">
            <span className="font-semibold">Upload Rejected: </span>
            {errorMessage}
          </div>
        </div>
      )}

      {lastSummary && (
        <div className="mt-4 p-4 rounded-xl bg-slate-800/80 border border-slate-700 space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-300">Import Summary</h3>
            <button
              onClick={() => setLastSummary(null)}
              className="text-xs text-slate-400 hover:text-white"
            >
              Dismiss
            </button>
          </div>

          <div className="grid grid-cols-3 gap-2.5">
            <div className="p-2.5 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-center">
              <span className="block text-lg font-bold text-emerald-400">{lastSummary.imported_count}</span>
              <span className="text-[11px] font-medium text-emerald-300/80">Imported</span>
            </div>
            <div className="p-2.5 rounded-lg bg-amber-500/10 border border-amber-500/20 text-center">
              <span className="block text-lg font-bold text-amber-400">{lastSummary.duplicate_count}</span>
              <span className="text-[11px] font-medium text-amber-300/80">Duplicates</span>
            </div>
            <div className="p-2.5 rounded-lg bg-red-500/10 border border-red-500/20 text-center">
              <span className="block text-lg font-bold text-red-400">{lastSummary.error_count}</span>
              <span className="text-[11px] font-medium text-red-300/80">Errors</span>
            </div>
          </div>

          {lastSummary.duplicates.length > 0 && (
            <div className="pt-2 border-t border-slate-700/60">
              <div className="text-xs font-medium text-amber-300 mb-1 flex items-center justify-between">
                <span>Skipped Duplicates ({lastSummary.duplicates.length})</span>
              </div>
              <ul className="text-[11px] space-y-1 text-slate-400 max-h-24 overflow-y-auto">
                {lastSummary.duplicates.map((dup, i) => (
                  <li key={i} className="flex gap-2">
                    <span className="font-mono text-amber-400/90 shrink-0">Line {dup.line}:</span>
                    <span>{dup.message}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {lastSummary.errors.length > 0 && (
            <div className="pt-2 border-t border-slate-700/60">
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs font-medium text-red-300">
                  Invalid Rows Skipped ({lastSummary.errors.length})
                </span>
                <button
                  onClick={() => setShowErrorDetails(!showErrorDetails)}
                  className="text-[11px] text-blue-400 hover:underline"
                >
                  {showErrorDetails ? 'Hide Details' : 'Show Details'}
                </button>
              </div>
              {showErrorDetails && (
                <ul className="text-[11px] space-y-1.5 text-slate-400 max-h-32 overflow-y-auto">
                  {lastSummary.errors.map((err, i) => (
                    <li key={i} className="p-1.5 rounded bg-red-500/5 border border-red-500/10 flex gap-2">
                      <span className="font-mono text-red-400 font-semibold shrink-0">Line {err.line}:</span>
                      <span className="text-slate-300">{err.message}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

