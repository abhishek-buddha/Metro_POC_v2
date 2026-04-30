// Three-dot menu component for employee actions
import React, { useState, useRef, useEffect } from 'react';
import { MoreVertical, Eye, ArrowRight, X } from 'lucide-react';

interface ThreeDotMenuProps {
  onViewDetails: () => void;
  onProceed: () => void;
  onCancel: () => void;
}

const ThreeDotMenu: React.FC<ThreeDotMenuProps> = ({
  onViewDetails,
  onProceed,
  onCancel,
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  return (
    <div className="relative" ref={menuRef}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="p-1 hover:bg-gray-100 rounded-lg transition-colors"
      >
        <MoreVertical size={16} className="text-gray-600" />
      </button>

      {isOpen && (
        <div className="absolute right-0 mt-2 w-48 bg-white rounded-lg shadow-lg border border-gray-200 py-1 z-50">
          <button
            onClick={() => {
              onViewDetails();
              setIsOpen(false);
            }}
            className="w-full px-4 py-2 text-left text-sm text-gray-700 hover:bg-gray-50 flex items-center space-x-2"
          >
            <Eye size={16} />
            <span>View Details</span>
          </button>
          <button
            onClick={() => {
              onProceed();
              setIsOpen(false);
            }}
            className="w-full px-4 py-2 text-left text-sm text-gray-700 hover:bg-gray-50 flex items-center space-x-2"
          >
            <ArrowRight size={16} />
            <span>Proceed</span>
          </button>
          <button
            onClick={() => {
              onCancel();
              setIsOpen(false);
            }}
            className="w-full px-4 py-2 text-left text-sm text-red-600 hover:bg-red-50 flex items-center space-x-2"
          >
            <X size={16} />
            <span>Delete</span>
          </button>
        </div>
      )}
    </div>
  );
};

export default ThreeDotMenu;
