// API service layer for Metro HRMS POC
import axios from 'axios';
import type { Submission } from './types';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
const API_KEY = import.meta.env.VITE_API_KEY || 'metro-kyc-secure-key-2026';

// Create axios instance with default config
const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
    'X-API-Key': API_KEY,
  },
});

// Helper to convert DD/MM/YYYY to YYYY-MM-DD
const convertDateFormat = (dateStr: string): string => {
  if (!dateStr) return '';
  // Handle DD/MM/YYYY format
  const parts = dateStr.split('/');
  if (parts.length === 3) {
    const [day, month, year] = parts;
    return `${year}-${month.padStart(2, '0')}-${day.padStart(2, '0')}`;
  }
  return dateStr;
};

// Convert an absolute server file path to a viewable URL
const toDocumentUrl = (filePath: string): string => {
  const normalized = filePath.replace(/\\/g, '/');
  const match = normalized.match(/uploads\/(.+)$/);
  return match ? `${API_BASE_URL}/uploads/${match[1]}` : '';
};

// Helper to map backend submission to frontend format
const mapSubmission = (backendData: any): Submission => {
  // Generate hardcoded fields for POC (fields not in documents)
  const fullName = backendData.pan_name || backendData.aadhaar_name || '';
  const nameForEmail = fullName.toLowerCase().replace(/\s+/g, '.');

  // Split address into lines, skipping C/O prefix lines
  const addressParts = (backendData.aadhaar_address || '')
    .split(',')
    .map((s: string) => s.trim())
    .filter((s: string) => !s.toLowerCase().startsWith('c/o'));

  return {
    id: backendData.id,
    temp_id: backendData.phone_number?.replace('+91', 'TEMP') || 'TEMP0000',
    employee_id: backendData.employee_id,
    phone_number: backendData.phone_number,
    aadhaar_name: backendData.aadhaar_name || '',
    aadhaar_last4: backendData.aadhaar_last4,
    aadhaar_dob: convertDateFormat(backendData.aadhaar_dob || ''),
    aadhaar_gender: backendData.aadhaar_gender,
    aadhaar_address: backendData.aadhaar_address,
    pan_name: backendData.pan_name || '',
    pan_number: backendData.pan_number || '',
    pan_dob: convertDateFormat(backendData.pan_dob || ''),
    pan_father_name: backendData.pan_father_name || '',
    gender: backendData.aadhaar_gender || backendData.gender || '',
    contact_number: backendData.phone_number || '',

    // Hardcoded fields for POC (not in documents)
    email: backendData.email || `${nameForEmail}@metrobrands.com`,
    personal_email: `${nameForEmail}@gmail.com`,
    blood_group: backendData.blood_group || '',
    marital_status: backendData.marital_status || '',
    spouse_name: '',
    official_email: `${nameForEmail}@metrobrands.com`,
    official_contact: backendData.phone_number || '',

    address: backendData.aadhaar_address || '',
    address_line1: addressParts[0] || '',
    address_line2: addressParts[1] || '',
    address_line3: addressParts[2] || '',
    address_line4: addressParts[3] || backendData.aadhaar_pincode || '',

    father_name: backendData.pan_father_name || '',
    bank_account_number: backendData.bank_account || '',
    bank_account: backendData.bank_account,
    ifsc_code: backendData.bank_ifsc || '',
    bank_ifsc: backendData.bank_ifsc,
    bank_name: backendData.bank_name || '',
    branch_name: backendData.bank_branch || '',
    bank_branch: backendData.bank_branch,

    // Document URLs - convert absolute server paths to viewable URLs via /uploads static route
    aadhaar_pdf_url: backendData.documents?.find((d: any) => d.document_type === 'AADHAAR_CARD')?.file_path
      ? toDocumentUrl(backendData.documents.find((d: any) => d.document_type === 'AADHAAR_CARD').file_path)
      : null,
    aadhaar_pdf_urls: (backendData.documents ?? [])
      .filter((d: any) => d.document_type === 'AADHAAR_CARD' && d.file_path)
      .map((d: any) => toDocumentUrl(d.file_path)),
    pan_pdf_url: backendData.documents?.find((d: any) => d.document_type === 'PAN_CARD')?.file_path
      ? toDocumentUrl(backendData.documents.find((d: any) => d.document_type === 'PAN_CARD').file_path)
      : null,
    cancelled_cheque_url: backendData.documents?.find((d: any) => d.document_type === 'BANK_DOCUMENT')?.file_path
      ? toDocumentUrl(backendData.documents.find((d: any) => d.document_type === 'BANK_DOCUMENT').file_path)
      : null,
    aadhaar_password: 'DOB123',

    status: backendData.status,
    submission_level: backendData.status === 'FINALIZED' ? 'Completed' : backendData.status === 'APPROVED' ? 'Basic Info' : 'Payroll',
    entity_name: 'Metro Brands Limited',
    created_at: backendData.submitted_at,
    updated_at: backendData.reviewed_at || backendData.submitted_at,
    submitted_at: backendData.submitted_at,
    reviewed_at: backendData.reviewed_at,
    reviewed_by: backendData.reviewed_by,
    finalized_at: backendData.finalized_at,
    finalized_by: backendData.finalized_by,
    hrms_employee_id: backendData.hrms_employee_id,
    documents: backendData.documents,
  };
};

// API service functions
export const submissionApi = {
  // Get all submissions
  getAll: async (): Promise<Submission[]> => {
    const response = await apiClient.get('/api/submissions');
    const submissions = response.data.submissions || [];
    return submissions.map(mapSubmission);
  },

  // Get single submission by ID
  getById: async (id: string): Promise<Submission> => {
    const response = await apiClient.get(`/api/submissions/${id}`);
    return mapSubmission(response.data);
  },

  // Save HR-edited form data
  update: async (id: string, data: any): Promise<any> => {
    const response = await apiClient.patch(`/api/submissions/${id}`, {
      first_name: data.firstName,
      full_name: data.fullName,
      dob: data.dob,
      gender: data.gender,
      blood_group: data.bloodGroup,
      marital_status: data.maritalStatus,
      father_name: data.fatherName,
      address_line1: data.addressLine1,
      address_line2: data.addressLine2,
      address_line3: data.addressLine3,
      address_line4: data.addressLine4,
      bank_account: data.accountNumber,
      ifsc_code: data.ifscCode,
      bank_name: data.bankName,
      bank_branch: data.branchAddress,
    });
    return response.data;
  },

  // Finalize submission
  finalize: async (id: string, data: any): Promise<any> => {
    const response = await apiClient.post(`/api/submissions/${id}/finalize`, data);
    return response.data;
  },

  // Delete submission
  delete: async (id: string): Promise<void> => {
    await apiClient.delete(`/api/submissions/${id}`);
  },
};

// Helper function to get display status
export const getDisplayStatus = (status: string): { text: string; color: string } => {
  switch (status) {
    case 'APPROVED':
      return { text: 'In Progress', color: 'orange' };
    case 'FINALIZED':
      return { text: 'Completed', color: 'green' };
    case 'REJECTED':
      return { text: 'Rejected', color: 'red' };
    default:
      return { text: 'Pending', color: 'gray' };
  }
};

// Helper function to calculate age from DOB
export const calculateAge = (dob: string): string => {
  if (!dob) return '';
  const birthDate = new Date(dob);
  const today = new Date();
  let age = today.getFullYear() - birthDate.getFullYear();
  const monthDiff = today.getMonth() - birthDate.getMonth();
  if (monthDiff < 0 || (monthDiff === 0 && today.getDate() < birthDate.getDate())) {
    age--;
  }
  return `${age} year(s) ${Math.abs(monthDiff)} month(s) ${Math.abs(today.getDate() - birthDate.getDate())} day(s)`;
};

// Helper function to get initials from name
export const getInitials = (name: string): string => {
  if (!name) return '?';
  const parts = name.trim().split(' ');
  if (parts.length === 1) return parts[0].charAt(0).toUpperCase();
  return (parts[0].charAt(0) + parts[parts.length - 1].charAt(0)).toUpperCase();
};

export default apiClient;

export interface UploadResponse {
  job_id: string;
  submission_id: string;
  status: string;
  message: string;
}

export interface JobStatusResponse {
  job_id: string;
  status: string;
  submission_id: string;
  document_type: string | null;
  message: string;
}

export const uploadApi = {
  uploadDocument: async (file: File, phoneNumber: string): Promise<UploadResponse> => {
    const form = new FormData();
    form.append('file', file);
    form.append('phone_number', phoneNumber);
    const response = await fetch(API_BASE_URL + '/api/upload/document', {
      method: 'POST',
      headers: { 'X-API-Key': API_KEY },
      body: form,
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || 'Upload failed (' + response.status + ')');
    }
    return response.json();
  },

  getJobStatus: async (jobId: string): Promise<JobStatusResponse> => {
    const response = await fetch(API_BASE_URL + '/api/upload/status/' + jobId, {
      headers: { 'X-API-Key': API_KEY },
    });
    if (!response.ok) throw new Error('Status check failed (' + response.status + ')');
    return response.json();
  },
};
