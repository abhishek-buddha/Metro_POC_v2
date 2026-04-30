import React, { useState, useRef, useCallback, useEffect } from 'react';
import { X, Upload, CheckCircle, AlertCircle, Loader, FileText } from 'lucide-react';
import { uploadApi } from '../utils/api';
import type { JobStatusResponse } from '../utils/api';

interface AddNewModalProps {
  onClose: () => void;
  onComplete: (submissionId: string) => void;
}

type FileStatus = 'uploading' | 'queued' | 'processing' | 'completed' | 'failed';

interface FileItem {
  id: string;
  name: string;
  status: FileStatus;
  jobId?: string;
  documentType?: string;
  error?: string;
}

const POLL_MS = 2500;

const STATUS_LABEL: Record<FileStatus, string> = {
  uploading:  'Uploading…',
  queued:     'Queued for processing…',
  processing: 'Extracting data with AI…',
  completed:  'Extracted successfully',
  failed:     'Failed — click × to remove',
};

const DOC_TYPE_LABEL: Record<string, string> = {
  PAN_CARD:      'PAN Card',
  AADHAAR_CARD:  'Aadhaar Card',
  BANK_DOCUMENT: 'Bank Document',
};

const AddNewModal: React.FC<AddNewModalProps> = ({ onClose, onComplete }) => {
  const [phone, setPhone]               = useState('');
  const [phoneError, setPhoneError]     = useState('');
  const [phoneReady, setPhoneReady]     = useState(false);
  const [files, setFiles]               = useState<FileItem[]>([]);
  const [submissionId, setSubmissionId] = useState<string | null>(null);
  const [drag, setDrag]                 = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const timers   = useRef<Record<string, ReturnType<typeof setInterval>>>({});

  useEffect(() => () => { Object.values(timers.current).forEach(clearInterval); }, []);

  const patchFile = useCallback((id: string, patch: Partial<FileItem>) =>
    setFiles(prev => prev.map(f => f.id === id ? { ...f, ...patch } : f)), []);

  const removeFile = useCallback((id: string) => {
    clearInterval(timers.current[id]);
    delete timers.current[id];
    setFiles(prev => prev.filter(f => f.id !== id));
  }, []);

  const handlePhoneSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const digits = phone.replace(/\D/g, '');
    if (digits.length < 7) { setPhoneError('Enter a valid phone number'); return; }
    setPhoneError(''); setPhoneReady(true);
  };

  const processFile = useCallback(async (file: File) => {
    const id = crypto.randomUUID();
    setFiles(prev => [...prev, { id, name: file.name, status: 'uploading' }]);

    try {
      const res = await uploadApi.uploadDocument(file, phone);
      setSubmissionId(prev => prev ?? res.submission_id);
      patchFile(id, { status: 'queued', jobId: res.job_id });

      const timer = setInterval(async () => {
        try {
          const st: JobStatusResponse = await uploadApi.getJobStatus(res.job_id);
          if (st.status === 'completed') {
            clearInterval(timers.current[id]); delete timers.current[id];
            patchFile(id, { status: 'completed', documentType: st.document_type ?? undefined });
          } else if (st.status === 'failed') {
            clearInterval(timers.current[id]); delete timers.current[id];
            patchFile(id, { status: 'failed', error: st.message });
          } else {
            patchFile(id, { status: st.status === 'queued' ? 'queued' : 'processing' });
          }
        } catch { /* network hiccup */ }
      }, POLL_MS);
      timers.current[id] = timer;
    } catch (err) {
      patchFile(id, { status: 'failed', error: err instanceof Error ? err.message : 'Upload failed. Please try again.' });
    }
  }, [phone, patchFile]);

  const handleFilePick = useCallback((picked: FileList | null) => {
    if (!picked || !phoneReady) return;
    Array.from(picked).forEach(processFile);
  }, [phoneReady, processFile]);

  const completedCount = files.filter(f => f.status === 'completed').length;
  const anyInFlight    = files.some(f => ['uploading','queued','processing'].includes(f.status));
  const canProceed     = completedCount > 0 && !anyInFlight && !!submissionId;

  const reset = () => {
    Object.values(timers.current).forEach(clearInterval);
    timers.current = {};
    setFiles([]); setSubmissionId(null); setPhoneReady(false); setPhone('');
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-xl flex flex-col max-h-[90vh]">

        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 flex-shrink-0">
          <div>
            <h2 className="text-base font-semibold text-gray-900">Add New Employee</h2>
            <p className="text-xs text-gray-500 mt-0.5">Upload KYC documents — AI extracts and classifies automatically</p>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-gray-100 transition-colors">
            <X className="w-5 h-5 text-gray-500" />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-6 py-5 space-y-6">

          {/* Step 1 — Phone */}
          <div>
            <div className="flex items-center gap-2 mb-3">
              <span className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0 ${phoneReady ? 'bg-green-500 text-white' : 'bg-indigo-600 text-white'}`}>
                {phoneReady ? '✓' : '1'}
              </span>
              <span className="text-sm font-semibold text-gray-700">Employee Phone Number</span>
            </div>
            {!phoneReady ? (
              <form onSubmit={handlePhoneSubmit} className="flex gap-2">
                <div className="flex-1">
                  <input type="tel" value={phone} onChange={e => { setPhone(e.target.value); setPhoneError(''); }}
                    placeholder="e.g. 9876543210" autoFocus
                    className={`w-full px-3 py-2 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 ${phoneError ? 'border-red-400' : 'border-gray-300'}`}
                  />
                  {phoneError && <p className="text-xs text-red-500 mt-1">{phoneError}</p>}
                </div>
                <button type="submit" className="px-4 py-2 bg-indigo-600 text-white text-sm font-medium rounded-lg hover:bg-indigo-700 transition-colors whitespace-nowrap">
                  Continue
                </button>
              </form>
            ) : (
              <div className="flex items-center justify-between bg-gray-50 border border-gray-200 rounded-lg px-3 py-2">
                <span className="text-sm font-mono text-gray-700">{phone}</span>
                <button onClick={reset} className="text-xs text-indigo-600 hover:underline">Change</button>
              </div>
            )}
          </div>

          {/* Step 2 — Documents */}
          <div>
            <div className="flex items-center gap-2 mb-3">
              <span className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0 ${completedCount > 0 && !anyInFlight ? 'bg-green-500 text-white' : phoneReady ? 'bg-indigo-600 text-white' : 'bg-gray-200 text-gray-500'}`}>
                {completedCount > 0 && !anyInFlight ? '✓' : '2'}
              </span>
              <span className="text-sm font-semibold text-gray-700">Upload Documents</span>
              {phoneReady && files.length > 0 && (
                <span className="ml-auto text-xs text-gray-400">{completedCount} / {files.length} processed</span>
              )}
            </div>

            {!phoneReady ? (
              <div className="rounded-xl border border-dashed border-gray-200 p-6 text-center text-sm text-gray-400">
                Complete step 1 to unlock document upload
              </div>
            ) : (
              <div className="space-y-3">
                {/* Drop zone */}
                <div
                  role="button"
                  tabIndex={0}
                  onDragOver={e => { e.preventDefault(); setDrag(true); }}
                  onDragLeave={() => setDrag(false)}
                  onDrop={e => { e.preventDefault(); setDrag(false); handleFilePick(e.dataTransfer.files); }}
                  onClick={() => inputRef.current?.click()}
                  onKeyDown={e => e.key === 'Enter' && inputRef.current?.click()}
                  className={`border-2 border-dashed rounded-xl px-4 py-6 text-center cursor-pointer transition-all duration-150 ${drag ? 'border-indigo-500 bg-indigo-50' : 'border-gray-300 bg-white hover:border-indigo-400 hover:bg-indigo-50'}`}
                >
                  <Upload className="w-6 h-6 text-indigo-400 mx-auto mb-2" />
                  <p className="text-sm font-medium text-gray-700">Click or drag &amp; drop files here</p>
                  <p className="text-xs text-gray-400 mt-1">
                    Select all documents at once — PAN, Aadhaar front, Aadhaar back, bank cheque, etc.
                  </p>
                  <p className="text-xs text-gray-400 mt-0.5">JPG, PNG, PDF · max 10 MB each</p>
                </div>
                <input
                  ref={inputRef}
                  type="file"
                  multiple
                  className="hidden"
                  accept=".jpg,.jpeg,.png,.webp,.tiff,.pdf,image/*,application/pdf"
                  onChange={e => { handleFilePick(e.target.files); e.target.value = ''; }}
                />

                {/* Per-file progress list */}
                {files.length > 0 && (
                  <div className="space-y-2 mt-1">
                    {files.map(f => (
                      <FileRow key={f.id} file={f} onRemove={() => removeFile(f.id)} />
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-gray-100 bg-gray-50 rounded-b-2xl flex items-center justify-between gap-3 flex-shrink-0">
          <p className="text-xs text-gray-400">
            {anyInFlight ? 'Processing, please wait…'
              : completedCount === 0 ? 'Upload at least one document to continue.'
              : `${completedCount} document${completedCount > 1 ? 's' : ''} ready for review.`}
          </p>
          <div className="flex gap-2">
            <button onClick={onClose} className="px-4 py-2 text-sm text-gray-600 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors">Cancel</button>
            <button disabled={!canProceed} onClick={() => canProceed && onComplete(submissionId!)}
              className={`px-4 py-2 text-sm font-semibold rounded-lg transition-all ${canProceed ? 'bg-indigo-600 text-white hover:bg-indigo-700 shadow-sm active:scale-95' : 'bg-gray-200 text-gray-400 cursor-not-allowed'}`}>
              View Employee →
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

// ── File Row ───────────────────────────────────────────────────────────────────
interface FileRowProps { file: FileItem; onRemove: () => void; }

const FileRow: React.FC<FileRowProps> = ({ file, onRemove }) => {
  const inProgress = ['uploading','queued','processing'].includes(file.status);

  const rowCls = file.status === 'completed' ? 'border-green-200 bg-green-50'
    : file.status === 'failed'               ? 'border-red-200 bg-red-50'
    : inProgress                             ? 'border-indigo-200 bg-indigo-50'
    :                                          'border-gray-200 bg-white';

  return (
    <div className={`flex items-center gap-3 border rounded-xl px-3 py-2.5 transition-colors ${rowCls}`}>
      {/* Icon */}
      <div className="flex-shrink-0">
        {inProgress
          ? <Loader className="w-4 h-4 text-indigo-500 animate-spin" />
          : file.status === 'completed'
            ? <CheckCircle className="w-4 h-4 text-green-500" />
            : file.status === 'failed'
              ? <AlertCircle className="w-4 h-4 text-red-500" />
              : <FileText className="w-4 h-4 text-gray-400" />}
      </div>

      {/* Name + status */}
      <div className="flex-1 min-w-0">
        <p className="text-xs font-medium text-gray-700 truncate">{file.name}</p>
        <p className={`text-xs mt-0.5 ${file.status === 'completed' ? 'text-green-600' : file.status === 'failed' ? 'text-red-500' : 'text-indigo-500'}`}>
          {STATUS_LABEL[file.status]}
        </p>
        {file.error && file.status === 'failed' && (
          <p className="text-xs text-red-400 mt-0.5">{file.error}</p>
        )}
      </div>

      {/* Detected type badge */}
      {file.status === 'completed' && file.documentType && (
        <span className="flex-shrink-0 text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded-full font-medium">
          {DOC_TYPE_LABEL[file.documentType] ?? file.documentType.replace(/_/g, ' ')}
        </span>
      )}

      {/* Remove button */}
      {!inProgress && (
        <button onClick={onRemove} className="flex-shrink-0 p-1 rounded hover:bg-black/5 text-gray-400 hover:text-gray-600 transition-colors" title="Remove">
          <X className="w-3.5 h-3.5" />
        </button>
      )}
    </div>
  );
};

export default AddNewModal;
