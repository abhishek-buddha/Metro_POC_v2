// File upload component
import React, { useRef } from 'react';
import { Upload, Eye, Trash2 } from 'lucide-react';

interface FileUploadProps {
  label: string;
  value: string | File | null;
  onChange: (file: File | null) => void;
  onView?: () => void;
  accept?: string;
  required?: boolean;
  maxSize?: string;
  allowedFormats?: string;
  existingFileUrl?: string;
}

const FileUpload: React.FC<FileUploadProps> = ({
  label,
  value,
  onChange,
  onView,
  accept = '.pdf,.jpg,.jpeg,.png',
  required = false,
  maxSize = '10 MB',
  allowedFormats = 'PDF',
  existingFileUrl,
}) => {
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      onChange(file);
    }
  };

  const handleClear = () => {
    onChange(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const hasFile = !!(value || existingFileUrl);
  const displayName = value instanceof File
    ? value.name
    : typeof value === 'string'
      ? value.split('/').pop() || value
      : existingFileUrl?.split('/').pop() || '';

  return (
    <div>
      <label className="block text-sm font-medium text-gray-700 mb-2">
        {label}
        {required && <span className="text-red-500 ml-1">*</span>}
      </label>

      {hasFile ? (
        <div className="border border-gray-300 rounded-lg p-3 flex items-center justify-between">
          <div className="flex items-center space-x-2 flex-1 min-w-0">
            <div className="text-indigo-600 flex-shrink-0">
              <Upload size={16} />
            </div>
            <span className="text-sm text-gray-700 truncate">{displayName}</span>
          </div>
          <div className="flex items-center space-x-2 ml-2">
            {onView && (
              <button
                type="button"
                onClick={onView}
                className="p-1 text-indigo-600 hover:bg-indigo-50 rounded"
                title="View document"
              >
                <Eye size={16} />
              </button>
            )}
            <button
              type="button"
              onClick={handleClear}
              className="p-1 text-red-600 hover:bg-red-50 rounded"
              title="Remove file"
            >
              <Trash2 size={16} />
            </button>
          </div>
        </div>
      ) : (
        <div>
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            className="w-full px-4 py-2 border border-gray-300 rounded-lg text-sm text-gray-700 hover:bg-gray-50 transition-colors flex items-center justify-center space-x-2"
          >
            <Upload size={16} />
            <span>Upload Attachment</span>
          </button>
          <p className="text-xs text-gray-500 mt-1">
            Maximum file size {maxSize} | Allowed formats: {allowedFormats}
          </p>
        </div>
      )}

      <input
        ref={fileInputRef}
        type="file"
        accept={accept}
        onChange={handleFileChange}
        className="hidden"
      />
    </div>
  );
};

export default FileUpload;
