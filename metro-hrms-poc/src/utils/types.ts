// Type definitions for Metro HRMS POC

export interface Submission {
  id: string;
  temp_id: string;
  employee_id: string;
  phone_number: string;
  aadhaar_name: string;
  aadhaar_last4?: string;
  aadhaar_dob?: string;
  aadhaar_gender?: string;
  aadhaar_address?: string | null;
  pan_name: string;
  pan_number: string;
  pan_dob: string;
  pan_father_name: string;
  gender: string;
  contact_number: string;
  email: string;
  address: string;
  father_name: string;
  bank_account_number: string;
  bank_account?: string | null;
  ifsc_code: string;
  bank_ifsc?: string | null;
  bank_name: string;
  branch_name: string;
  bank_branch?: string | null;
  aadhaar_pdf_url: string | null;
  aadhaar_pdf_urls: Array<{ url: string; side: 'front' | 'back' | 'both' | null }>;
  pan_pdf_url: string | null;
  cancelled_cheque_url: string | null;

  // Additional fields for POC
  personal_email?: string;
  blood_group?: string;
  marital_status?: string;
  spouse_name?: string;
  official_email?: string;
  official_contact?: string;
  address_line1?: string;
  address_line2?: string;
  address_line3?: string;
  address_line4?: string;
  aadhaar_password?: string;

  previously_worked?: string;
  previous_employee_id?: string;

  status: 'PENDING' | 'APPROVED' | 'REJECTED' | 'FINALIZED';
  submission_level: string;
  entity_name: string;
  created_at?: string;
  updated_at?: string;
  submitted_at?: string;
  reviewed_at?: string | null;
  reviewed_by?: string | null;
  finalized_at?: string | null;
  finalized_by?: string | null;
  hrms_employee_id?: string | null;
  documents?: Array<{
    id: string;
    document_type: string;
    file_path: string;
    uploaded_at: string;
    aadhaar_side?: 'front' | 'back' | 'both' | null;
  }>;
}

export interface EmployeeFormData {
  // Personal Details
  firstName: string;
  fullName: string;
  dob: string;
  gender: string;
  bloodGroup: string;
  maritalStatus: string;
  contactNumber: string;
  personalEmail: string;
  officialEmail: string;
  officialContactNumber: string;
  addressLine1: string;
  addressLine2: string;
  addressLine3: string;
  addressLine4: string;
  age: string;
  spouseName: string;

  // Financial Details
  aadhaarUpload: string | null;
  fatherName: string;
  panUpload: string | null;
  eAadhaarPassword: string;

  // Bank Details
  accountNumber: string;
  ifscCode: string;
  bankName: string;
  branchAddress: string;
  chequeUpload: string | null;

  // Other Details
  resume: string | null;
  educationalDocs: string | null;
  profilePhoto: string | null;
  napsLetter: string | null;
  signatureAttachment: string | null;
  grade: string;
  division: string;
  category: string;

  // Previous Employment
  previouslyWorked: string;
  previousEmployeeId: string;

  // Educational Documents
  edu10th: string | null;
  edu12th: string | null;
  eduGraduation: string | null;
  eduPostGraduation: string | null;
}

export interface FilterState {
  submissionStatus: string;
  submissionLevel: string;
}

export interface DocumentViewerProps {
  isOpen: boolean;
  onClose: () => void;
  documentUrl: string;
  documentName: string;
  requiresPassword?: boolean;
}
