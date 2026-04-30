// Employee form page with multi-step stepper
import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Check, Info, Eye, FileText } from 'lucide-react';
import FileUpload from '../components/FileUpload';
import DocumentViewer from '../components/DocumentViewer';
import type { Submission, EmployeeFormData } from '../utils/types';
import { submissionApi, calculateAge } from '../utils/api';

const EmployeeForm: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [currentStep, setCurrentStep] = useState(1);
  const [loading, setLoading] = useState(true);
  const [submission, setSubmission] = useState<Submission | null>(null);
  const [formData, setFormData] = useState<EmployeeFormData>({
    firstName: '',
    fullName: '',
    dob: '',
    gender: '',
    bloodGroup: '',
    maritalStatus: '',
    contactNumber: '',
    personalEmail: '',
    officialEmail: '',
    officialContactNumber: '',
    addressLine1: '',
    addressLine2: '',
    addressLine3: '',
    addressLine4: '',
    age: '',
    spouseName: '',
    aadhaarUpload: null,
    fatherName: '',
    panUpload: null,
    eAadhaarPassword: '',
    accountNumber: '',
    ifscCode: '',
    bankName: '',
    branchAddress: '',
    chequeUpload: null,
    resume: null,
    educationalDocs: null,
    profilePhoto: null,
    napsLetter: null,
    signatureAttachment: null,
    grade: '',
    division: '',
    category: '',
  });
  const [documentViewer, setDocumentViewer] = useState({
    isOpen: false,
    url: '',
    name: '',
    requiresPassword: false,
  });

  const steps = [
    { number: 1, title: 'Personal Details', completed: false },
    { number: 2, title: 'Company Structure & Policies', completed: false },
    { number: 3, title: 'Payroll', completed: false },
  ];

  useEffect(() => {
    if (id) {
      fetchSubmission(id);
    }
  }, [id]);

  useEffect(() => {
    if (formData.dob) {
      setFormData((prev) => ({
        ...prev,
        age: calculateAge(prev.dob),
      }));
    }
  }, [formData.dob]);

  const fetchSubmission = async (submissionId: string) => {
    try {
      setLoading(true);
      const data = await submissionApi.getById(submissionId);
      console.log('📊 Submission data received:', data);
      console.log('📧 Personal Email:', data.personal_email);
      console.log('🩸 Blood Group:', data.blood_group);
      console.log('💍 Marital Status:', data.marital_status);
      setSubmission(data);

      // Pre-populate form with submission data
      setFormData({
        // FROM WHATSAPP DOCUMENTS:
        firstName: data.aadhaar_name || data.pan_name || '',  // From Aadhaar, fallback PAN
        fullName: data.pan_name || data.aadhaar_name || '',  // From PAN, fallback Aadhaar
        dob: data.pan_dob || data.aadhaar_dob || '',  // From PAN or Aadhaar
        gender: data.gender || '',  // From Aadhaar
        fatherName: data.father_name || '',  // From PAN
        accountNumber: data.bank_account_number || '',  // From Bank Statement
        ifscCode: data.ifsc_code || '',  // From Bank Statement
        bankName: data.bank_name || '',  // From Bank Statement
        branchAddress: data.branch_name || '',  // From Bank Statement

        // HARDCODED FOR POC (not from documents):
        bloodGroup: data.blood_group || '',
        maritalStatus: data.marital_status || 'Single',
        contactNumber: data.contact_number || '',
        personalEmail: data.personal_email || '',
        officialEmail: data.official_email || '',
        officialContactNumber: data.official_contact || data.contact_number || '',
        addressLine1: data.address_line1 || '',
        addressLine2: data.address_line2 || '',
        addressLine3: data.address_line3 || '',
        addressLine4: data.address_line4 || '',
        age: data.pan_dob ? calculateAge(data.pan_dob) : '',
        spouseName: data.spouse_name || '',

        // DOCUMENTS (hardcoded URLs for POC):
        aadhaarUpload: data.aadhaar_pdf_url || null,
        panUpload: data.pan_pdf_url || null,
        eAadhaarPassword: data.aadhaar_password || 'DOB123',
        chequeUpload: data.cancelled_cheque_url || null,

        // OTHER (empty for POC):
        resume: null,
        educationalDocs: null,
        profilePhoto: null,
        napsLetter: null,
        signatureAttachment: null,
        grade: '',
        division: '',
        category: '',
      });
    } catch (err) {
      console.error('Error fetching submission:', err);
      alert('Failed to fetch submission details');
    } finally {
      setLoading(false);
    }
  };

  const handleInputChange = (
    field: keyof EmployeeFormData,
    value: string | File | null
  ) => {
    setFormData((prev) => ({
      ...prev,
      [field]: value,
    }));
  };

  const handleViewDocument = (url: string, name: string, requiresPassword = false) => {
    setDocumentViewer({
      isOpen: true,
      url,
      name,
      requiresPassword,
    });
  };

  const handleProceed = () => {
    if (currentStep < 3) {
      setCurrentStep(currentStep + 1);
    } else {
      handleSubmit();
    }
  };

  const handleSubmit = async () => {
    try {
      if (!id) return;
      await submissionApi.update(id, formData);
      await submissionApi.finalize(id, { finalized_by: 'hr_user' });
      alert('Employee form submitted successfully!');
      navigate('/');
    } catch (err) {
      console.error('Error submitting form:', err);
      alert('Failed to submit form');
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-gray-500">Loading...</div>
      </div>
    );
  }

  return (
    <div className="p-6 bg-gray-50">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-semibold text-gray-900">Employee Form</h1>
        <p className="text-sm text-gray-500 mt-1">
          {submission?.temp_id} | {submission?.aadhaar_name || submission?.pan_name}
        </p>
      </div>

      {/* Info Banner */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-6 flex items-start space-x-3">
        <Info className="w-5 h-5 text-blue-600 flex-shrink-0 mt-0.5" />
        <p className="text-sm text-blue-900">
          Employee's information will become active next the date of onboarding
        </p>
      </div>

      {/* Stepper */}
      <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-6 mb-6">
        <div className="flex items-center justify-between max-w-3xl mx-auto">
          {steps.map((step, index) => (
            <React.Fragment key={step.number}>
              <div className="flex flex-col items-center">
                <div
                  className={`w-10 h-10 rounded-full flex items-center justify-center font-medium transition-colors ${
                    currentStep > step.number
                      ? 'bg-green-500 text-white'
                      : currentStep === step.number
                      ? 'bg-indigo-600 text-white'
                      : 'bg-gray-200 text-gray-600'
                  }`}
                >
                  {currentStep > step.number ? (
                    <Check size={20} />
                  ) : (
                    step.number
                  )}
                </div>
                <span
                  className={`text-sm mt-2 font-medium ${
                    currentStep === step.number
                      ? 'text-indigo-600'
                      : 'text-gray-600'
                  }`}
                >
                  {step.title}
                </span>
              </div>
              {index < steps.length - 1 && (
                <div
                  className={`flex-1 h-1 mx-4 rounded transition-colors ${
                    currentStep > step.number ? 'bg-green-500' : 'bg-gray-200'
                  }`}
                />
              )}
            </React.Fragment>
          ))}
        </div>
      </div>

      {/* Form Content */}
      <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-6">
        {currentStep === 1 && (
          <div className="space-y-8">
            {/* Personal Details Section */}
            <div>
              <div className="grid grid-cols-2 gap-6">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    First Name <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="text"
                    value={formData.firstName}
                    onChange={(e) => handleInputChange('firstName', e.target.value)}
                    className="w-full px-3 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500 text-sm"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Full Name <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="text"
                    value={formData.fullName}
                    onChange={(e) => handleInputChange('fullName', e.target.value)}
                    className="w-full px-3 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500 text-sm"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    DOB <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="date"
                    value={formData.dob}
                    onChange={(e) => handleInputChange('dob', e.target.value)}
                    className="w-full px-3 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500 text-sm"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Gender <span className="text-red-500">*</span>
                  </label>
                  <select
                    value={formData.gender}
                    onChange={(e) => handleInputChange('gender', e.target.value)}
                    className="w-full px-3 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500 text-sm"
                  >
                    <option value="">Select Gender</option>
                    <option value="Male">Male</option>
                    <option value="Female">Female</option>
                    <option value="Other">Other</option>
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Blood Group
                  </label>
                  <select
                    value={formData.bloodGroup}
                    onChange={(e) => handleInputChange('bloodGroup', e.target.value)}
                    className="w-full px-3 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500 text-sm"
                  >
                    <option value="">Select</option>
                    <option value="A+">A+</option>
                    <option value="A-">A-</option>
                    <option value="B+">B+</option>
                    <option value="B-">B-</option>
                    <option value="O+">O+</option>
                    <option value="O-">O-</option>
                    <option value="AB+">AB+</option>
                    <option value="AB-">AB-</option>
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Marital Status <span className="text-red-500">*</span>
                  </label>
                  <select
                    value={formData.maritalStatus}
                    onChange={(e) => handleInputChange('maritalStatus', e.target.value)}
                    className="w-full px-3 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500 text-sm"
                  >
                    <option value="">Select</option>
                    <option value="Single">Single</option>
                    <option value="Married">Married</option>
                    <option value="Prefer not to say">Prefer not to say</option>
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Official Email
                  </label>
                  <input
                    type="email"
                    value={formData.officialEmail}
                    onChange={(e) => handleInputChange('officialEmail', e.target.value)}
                    placeholder="Enter Official Email"
                    className="w-full px-3 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500 text-sm"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Official Contact Number
                  </label>
                  <input
                    type="tel"
                    value={formData.officialContactNumber}
                    onChange={(e) => handleInputChange('officialContactNumber', e.target.value)}
                    className="w-full px-3 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500 text-sm"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Personal Email <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="email"
                    value={formData.personalEmail}
                    onChange={(e) => handleInputChange('personalEmail', e.target.value)}
                    className="w-full px-3 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500 text-sm"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Personal Contact Number <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="tel"
                    value={formData.contactNumber}
                    onChange={(e) => handleInputChange('contactNumber', e.target.value)}
                    className="w-full px-3 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500 text-sm"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Address Line 1 <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="text"
                    value={formData.addressLine1}
                    onChange={(e) => handleInputChange('addressLine1', e.target.value)}
                    className="w-full px-3 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500 text-sm"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Address Line 2
                  </label>
                  <input
                    type="text"
                    value={formData.addressLine2}
                    onChange={(e) => handleInputChange('addressLine2', e.target.value)}
                    placeholder="Enter Address Line 2"
                    className="w-full px-3 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500 text-sm"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Address line 3
                  </label>
                  <input
                    type="text"
                    value={formData.addressLine3}
                    onChange={(e) => handleInputChange('addressLine3', e.target.value)}
                    placeholder="Enter Address line 3"
                    className="w-full px-3 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500 text-sm"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Address Line 4
                  </label>
                  <input
                    type="text"
                    value={formData.addressLine4}
                    onChange={(e) => handleInputChange('addressLine4', e.target.value)}
                    className="w-full px-3 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500 text-sm"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Age
                  </label>
                  <input
                    type="text"
                    value={formData.age}
                    readOnly
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg bg-gray-50"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Spouse Name <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="text"
                    value={formData.spouseName}
                    onChange={(e) => handleInputChange('spouseName', e.target.value)}
                    placeholder="s"
                    className="w-full px-3 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500 text-sm"
                  />
                </div>
              </div>
            </div>

            {/* Financial Details Section */}
            <div>
              <h3 className="text-lg font-semibold text-gray-900 mb-4 border-b pb-2">
                Financial details
              </h3>
              <div className="grid grid-cols-2 gap-6">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    E Aadhar Card Upload <span className="text-red-500">*</span>
                  </label>
                  {submission?.aadhaar_pdf_urls && submission.aadhaar_pdf_urls.length > 0 ? (
                    <div className="space-y-2">
                      {submission.aadhaar_pdf_urls.map((item, idx) => {
                        const sideLabel =
                          item.side === 'both'  ? 'Both Sides' :
                          item.side === 'front' ? 'Front Side' :
                          item.side === 'back'  ? 'Back Side'  :
                          submission.aadhaar_pdf_urls.length > 1 ? `Side ${idx + 1}` : '';
                        return (
                          <div key={idx} className="border border-gray-300 rounded-lg p-3 flex items-center justify-between">
                            <div className="flex items-center space-x-2 flex-1 min-w-0">
                              <FileText size={16} className="text-indigo-600 flex-shrink-0" />
                              <span className="text-sm text-gray-700 truncate">
                                Aadhaar Card {sideLabel ? `(${sideLabel})` : ''}
                              </span>
                            </div>
                            <button
                              type="button"
                              onClick={() => handleViewDocument(item.url, `Aadhaar Card ${idx + 1}`, true)}
                              className="p-1 text-indigo-600 hover:bg-indigo-50 rounded ml-2"
                              title="View document"
                            >
                              <Eye size={16} />
                            </button>
                          </div>
                        );
                      })}
                    </div>
                  ) : (
                    <div className="border border-dashed border-gray-300 rounded-lg p-3 text-sm text-gray-400 text-center">
                      No Aadhaar documents uploaded
                    </div>
                  )}
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Father Name <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="text"
                    value={formData.fatherName}
                    onChange={(e) => handleInputChange('fatherName', e.target.value)}
                    className="w-full px-3 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500 text-sm"
                  />
                </div>

                <FileUpload
                  label="Pan Card Upload"
                  value={formData.panUpload}
                  onChange={(file) => handleInputChange('panUpload', file)}
                  onView={
                    formData.panUpload
                      ? () =>
                          handleViewDocument(
                            formData.panUpload || submission?.pan_pdf_url || '',
                            'PAN Card'
                          )
                      : undefined
                  }
                  existingFileUrl={submission?.pan_pdf_url || undefined}
                  required
                />

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    E-Aadhar Password <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="text"
                    value={formData.eAadhaarPassword}
                    onChange={(e) => handleInputChange('eAadhaarPassword', e.target.value)}
                    className="w-full px-3 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500 text-sm"
                  />
                </div>
              </div>
            </div>

            {/* Bank Details Section */}
            <div>
              <h3 className="text-lg font-semibold text-gray-900 mb-4 border-b pb-2">
                Bank Details
              </h3>
              <div className="grid grid-cols-2 gap-6">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Account Number <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="text"
                    value={formData.accountNumber}
                    onChange={(e) => handleInputChange('accountNumber', e.target.value)}
                    className="w-full px-3 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500 text-sm"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    IFSC Code <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="text"
                    value={formData.ifscCode}
                    onChange={(e) => handleInputChange('ifscCode', e.target.value)}
                    className="w-full px-3 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500 text-sm"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Bank Name
                  </label>
                  <input
                    type="text"
                    value={formData.bankName}
                    onChange={(e) => handleInputChange('bankName', e.target.value)}
                    className="w-full px-3 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500 text-sm"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Bank Branch Address <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="text"
                    value={formData.branchAddress}
                    onChange={(e) => handleInputChange('branchAddress', e.target.value)}
                    className="w-full px-3 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500 text-sm"
                  />
                </div>

                <FileUpload
                  label="Cancelled Cheque Upload"
                  value={formData.chequeUpload}
                  onChange={(file) => handleInputChange('chequeUpload', file)}
                  onView={
                    formData.chequeUpload
                      ? () =>
                          handleViewDocument(
                            formData.chequeUpload || submission?.cancelled_cheque_url || '',
                            'Cancelled Cheque'
                          )
                      : undefined
                  }
                  existingFileUrl={submission?.cancelled_cheque_url || undefined}
                  allowedFormats="PDF"
                />
              </div>
            </div>

            {/* Other Details Section */}
            <div>
              <h3 className="text-lg font-semibold text-gray-900 mb-4 border-b pb-2">
                Other Details
              </h3>
              <div className="grid grid-cols-2 gap-6">
                <FileUpload
                  label="Resume"
                  value={formData.resume}
                  onChange={(file) => handleInputChange('resume', file)}
                  allowedFormats="PDF"
                />

                <FileUpload
                  label="Educational Documents Upload"
                  value={formData.educationalDocs}
                  onChange={(file) => handleInputChange('educationalDocs', file)}
                  required
                />

                <FileUpload
                  label="Profile Photo"
                  value={formData.profilePhoto}
                  onChange={(file) => handleInputChange('profilePhoto', file)}
                  accept=".jpg,.jpeg,.png"
                  allowedFormats="JPG, JPEG"
                  required
                />

                <FileUpload
                  label="NAPS Authorization Letter"
                  value={formData.napsLetter}
                  onChange={(file) => handleInputChange('napsLetter', file)}
                  required
                />

                <FileUpload
                  label="Signature Attachment"
                  value={formData.signatureAttachment}
                  onChange={(file) => handleInputChange('signatureAttachment', file)}
                  accept=".jpg,.jpeg,.png"
                  allowedFormats="JPG, JPEG"
                  required
                />

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Grade
                  </label>
                  <select
                    value={formData.grade}
                    onChange={(e) => handleInputChange('grade', e.target.value)}
                    className="w-full px-3 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500 text-sm"
                  >
                    <option value="">Select Grade</option>
                    <option value="A">A</option>
                    <option value="B">B</option>
                    <option value="C">C</option>
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Division
                  </label>
                  <select
                    value={formData.division}
                    onChange={(e) => handleInputChange('division', e.target.value)}
                    className="w-full px-3 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500 text-sm"
                  >
                    <option value="">Select Division</option>
                    <option value="Sales">Sales</option>
                    <option value="Marketing">Marketing</option>
                    <option value="Operations">Operations</option>
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Category
                  </label>
                  <select
                    value={formData.category}
                    onChange={(e) => handleInputChange('category', e.target.value)}
                    className="w-full px-3 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500 text-sm"
                  >
                    <option value="">Select Category</option>
                    <option value="General">General</option>
                    <option value="OBC">OBC</option>
                    <option value="SC">SC</option>
                    <option value="ST">ST</option>
                  </select>
                </div>
              </div>
            </div>
          </div>
        )}

        {currentStep === 2 && (
          <div className="space-y-6">
            <div className="text-center py-12">
              <h3 className="text-lg font-semibold text-gray-900 mb-2">
                Company Structure & Policies
              </h3>
              <p className="text-gray-600">
                This section will contain company structure and policy information.
              </p>
            </div>
          </div>
        )}

        {currentStep === 3 && (
          <div className="space-y-6">
            <div className="text-center py-12">
              <h3 className="text-lg font-semibold text-gray-900 mb-2">
                Payroll Information
              </h3>
              <p className="text-gray-600">
                This section will contain payroll and compensation details.
              </p>
            </div>
          </div>
        )}

        {/* Form Actions */}
        <div className="flex justify-end space-x-4 mt-8 pt-6 border-t border-gray-200">
          <button
            onClick={() => navigate('/')}
            className="px-6 py-2.5 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 transition-colors text-sm font-medium"
          >
            Cancel
          </button>
          {currentStep > 1 && (
            <button
              onClick={() => setCurrentStep(currentStep - 1)}
              className="px-6 py-2.5 border border-indigo-600 text-indigo-600 rounded-lg hover:bg-indigo-50 transition-colors text-sm font-medium"
            >
              Back
            </button>
          )}
          <button
            onClick={handleProceed}
            className="px-8 py-2.5 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors text-sm font-medium shadow-sm"
          >
            {currentStep === 3 ? 'Submit' : 'Proceed'}
          </button>
        </div>
      </div>

      {/* Document Viewer Modal */}
      <DocumentViewer
        isOpen={documentViewer.isOpen}
        onClose={() =>
          setDocumentViewer({ isOpen: false, url: '', name: '', requiresPassword: false })
        }
        documentUrl={documentViewer.url}
        documentName={documentViewer.name}
        requiresPassword={documentViewer.requiresPassword}
      />
    </div>
  );
};

export default EmployeeForm;
