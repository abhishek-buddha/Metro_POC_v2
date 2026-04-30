// Employee list page with filters and table
import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Plus } from 'lucide-react';
import FilterPanel from '../components/FilterPanel';
import ThreeDotMenu from '../components/ThreeDotMenu';
import type { Submission, FilterState } from '../utils/types';
import { submissionApi, getDisplayStatus, getInitials } from '../utils/api';
import AddNewModal from '../components/AddNewModal';

const EmployeeList: React.FC = () => {
  const navigate = useNavigate();
  const [submissions, setSubmissions] = useState<Submission[]>([]);
  const [filteredSubmissions, setFilteredSubmissions] = useState<Submission[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filters, setFilters] = useState<FilterState>({
    submissionStatus: '',
    submissionLevel: '',
  });
  const [activeTab, setActiveTab] = useState('Onboarding');
  const [showModal, setShowModal] = useState(false);

  const tabs = [
    'Employee',
    'Onboarding',
    'Probation',
    'Access Management',
    'Skills & Competencies',
    'Position',
    'HR Policies',
  ];

  useEffect(() => {
    fetchSubmissions();
  }, []);

  const fetchSubmissions = async () => {
    try {
      setLoading(true);
      const data = await submissionApi.getAll();
      setSubmissions(data);
      setFilteredSubmissions(data);
      setError(null);
    } catch (err) {
      setError('Failed to fetch submissions');
      console.error('Error fetching submissions:', err);
    } finally {
      setLoading(false);
    }
  };

  const applyFilters = () => {
    let filtered = [...submissions];

    if (filters.submissionStatus) {
      filtered = filtered.filter(
        (s) => s.status === filters.submissionStatus
      );
    }

    if (filters.submissionLevel) {
      filtered = filtered.filter(
        (s) => s.submission_level === filters.submissionLevel
      );
    }

    setFilteredSubmissions(filtered);
  };

  const handleProceed = (id: string) => {
    navigate(`/employee/${id}/form`);
  };

  const handleViewDetails = (id: string) => {
    navigate(`/employee/${id}/form`);
  };

  const handleCancel = async (id: string) => {
    if (!confirm('Are you sure you want to delete this submission? This cannot be undone.')) return;
    try {
      await submissionApi.delete(id);
      setSubmissions((prev) => prev.filter((s) => s.id !== id));
      setFilteredSubmissions((prev) => prev.filter((s) => s.id !== id));
    } catch (err) {
      console.error('Error deleting submission:', err);
      alert('Failed to delete submission. Please try again.');
    }
  };

  return (
    <div className="p-6 bg-gray-50">
      {/* Page Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-semibold text-gray-900 mb-4">
          Add Employees List
        </h1>

        {/* Tabs */}
        <div className="flex space-x-8 border-b border-gray-200">
          {tabs.map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`px-1 py-3 text-sm font-medium transition-colors relative ${
                activeTab === tab
                  ? 'text-indigo-600'
                  : 'text-gray-600 hover:text-gray-900'
              }`}
            >
              {tab}
              {activeTab === tab && (
                <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-indigo-600" />
              )}
            </button>
          ))}
        </div>

        {/* Sub-tabs */}
        <div className="flex space-x-8 mt-6">
          <button className="text-sm font-medium text-indigo-600 border-b-2 border-indigo-600 pb-2">
            Add Employees
          </button>
          <button className="text-sm font-medium text-gray-600 hover:text-gray-900 pb-2">
            Bulk Uploads
          </button>
          <button className="text-sm font-medium text-gray-600 hover:text-gray-900 pb-2">
            Requests
          </button>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex space-x-6">
        {/* Left Sidebar - Filters */}
        <div className="w-60 flex-shrink-0">
          <FilterPanel
            filters={filters}
            onFilterChange={setFilters}
            onApply={applyFilters}
          />
        </div>

        {/* Right Content - Table */}
        <div className="flex-1">
          <div className="bg-white rounded-lg border border-gray-200 shadow-sm">
            {/* Table Header */}
            <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
              <h2 className="text-lg font-semibold text-gray-900">
                Add Employees List
              </h2>
              <button onClick={() => setShowModal(true)} className="flex items-center space-x-2 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors text-sm font-medium">
                <Plus size={18} />
                <span>Add New</span>
              </button>
            </div>

            {/* Table */}
            {loading ? (
              <div className="p-12 text-center text-gray-500">Loading...</div>
            ) : error ? (
              <div className="p-12 text-center text-red-500">{error}</div>
            ) : filteredSubmissions.length === 0 ? (
              <div className="p-12 text-center text-gray-500">
                No submissions found
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead className="bg-gray-50 border-b border-gray-200">
                    <tr>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Employee Name
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Temp ID
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Employee ID
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Entity Name
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Submission Status
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Submission Level
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Actions
                      </th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {filteredSubmissions.map((submission) => {
                      const status = getDisplayStatus(submission.status);
                      return (
                        <tr
                          key={submission.id}
                          className="hover:bg-gray-50 transition-colors"
                        >
                          <td className="px-6 py-4 whitespace-nowrap">
                            <div className="flex items-center space-x-3">
                              <div className="w-10 h-10 bg-indigo-600 rounded-full flex items-center justify-center flex-shrink-0">
                                <span className="text-white text-sm font-semibold">
                                  {getInitials(submission.aadhaar_name || submission.pan_name)}
                                </span>
                              </div>
                              <span className="text-sm font-medium text-gray-900">
                                {submission.aadhaar_name || submission.pan_name}
                              </span>
                            </div>
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                            {submission.temp_id}
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                            {submission.hrms_employee_id || submission.id.substring(0, 8)}
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                            {submission.entity_name}
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap">
                            <span
                              className={`inline-flex px-3 py-1 text-xs font-semibold rounded-full ${
                                status.color === 'orange'
                                  ? 'bg-orange-100 text-orange-700'
                                  : status.color === 'green'
                                  ? 'bg-green-100 text-green-700'
                                  : status.color === 'red'
                                  ? 'bg-red-100 text-red-700'
                                  : 'bg-gray-100 text-gray-700'
                              }`}
                            >
                              {status.text}
                            </span>
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                            {submission.submission_level}
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm">
                            <ThreeDotMenu
                              onViewDetails={() => handleViewDetails(submission.id)}
                              onProceed={() => handleProceed(submission.id)}
                              onCancel={() => handleCancel(submission.id)}
                            />
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}

            {/* Table Footer */}
            {!loading && !error && filteredSubmissions.length > 0 && (
              <div className="px-6 py-4 border-t border-gray-200 flex items-center justify-between">
                <div className="text-sm text-gray-600">
                  Showing 1 to {filteredSubmissions.length} of {filteredSubmissions.length} items
                </div>
                <div className="flex space-x-2">
                  <button className="px-3 py-1 border border-gray-300 rounded hover:bg-gray-50 text-sm">
                    Previous
                  </button>
                  <button className="px-3 py-1 bg-indigo-600 text-white rounded text-sm">
                    1
                  </button>
                  <button className="px-3 py-1 border border-gray-300 rounded hover:bg-gray-50 text-sm">
                    Next
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
      {showModal && (
        <AddNewModal
          onClose={() => setShowModal(false)}
          onComplete={(submissionId) => {
            setShowModal(false);
            fetchSubmissions();
            navigate('/employee/' + submissionId + '/form');
          }}
        />
      )}
    </div>
  );
};

export default EmployeeList;

