import React, { useState, useEffect } from 'react';
import { branchesAPI, modulesAPI } from '../../services/api';
import { toast } from '../../utils/toast';
import './BranchSelector.css';

const BranchSelector = ({ onBranchChange, showAllOption = false }) => {
  const [branches, setBranches] = useState([]);
  const [selectedBranch, setSelectedBranch] = useState(null);
  const [showDropdown, setShowDropdown] = useState(false);
  const [loading, setLoading] = useState(true);
  const [branchSupportEnabled, setBranchSupportEnabled] = useState(false);

  useEffect(() => {
    checkBranchSupport();
  }, []);

  useEffect(() => {
    // Only load branches if branch support is enabled
    if (branchSupportEnabled) {
      loadBranches();
    } else {
      // Branch support disabled - don't load branches
      setBranches([]);
      setLoading(false);
    }
  }, [branchSupportEnabled]);

  const checkBranchSupport = async () => {
    try {
      const response = await modulesAPI.list();
      const modulesData = response.data || {};
      const settingsModule = modulesData['settings'];
      const multiBranchFeature = settingsModule?.features?.multi_branch_support;
      const enabled = multiBranchFeature?.is_enabled || false;
      setBranchSupportEnabled(enabled);
      
      if (!enabled) {
        console.info('Multi-branch support is disabled in module settings');
      }
    } catch (error) {
      console.error('Error checking branch support:', error);
      // Default to disabled if check fails
      setBranchSupportEnabled(false);
    }
  };

  useEffect(() => {
    if (branches.length > 0 && !selectedBranch) {
      loadCurrentBranch();
    }
  }, [branches]);

  const loadBranches = async () => {
    // Don't load branches if branch support is disabled
    if (!branchSupportEnabled) {
      setBranches([]);
      setLoading(false);
      return;
    }
    
    try {
      const response = await branchesAPI.active();
      const branchesData = response.data || [];
      setBranches(branchesData);
      
      // If no branches, show helpful message
      if (branchesData.length === 0) {
        console.info('No branches found - add branches through module settings');
      }
    } catch (error) {
      console.error('Error loading branches:', error);
      // Don't show error if it's just that there are no branches or CORS issue
      if (error.response?.status !== 404 && error.code !== 'ERR_NETWORK') {
        toast.error('Failed to load branches');
      }
      setBranches([]); // Set empty array on error
    } finally {
      setLoading(false);
    }
  };

  const loadCurrentBranch = async () => {
    const storedBranch = localStorage.getItem('current_branch');
    if (storedBranch) {
      try {
        const branch = JSON.parse(storedBranch);
        // Verify branch still exists and is active
        const branchExists = branches.find(b => b.id === branch.id);
        if (branchExists) {
          setSelectedBranch(branch);
          if (onBranchChange) {
            onBranchChange(branch);
          }
          return;
        }
      } catch (e) {
        console.error('Error parsing stored branch:', e);
      }
    }
    
    // Try to get headquarters
    try {
      const hqResponse = await branchesAPI.headquarters();
      if (hqResponse.data) {
        setSelectedBranch(hqResponse.data);
        localStorage.setItem('current_branch', JSON.stringify(hqResponse.data));
        if (onBranchChange) {
          onBranchChange(hqResponse.data);
        }
      }
    } catch {
      // No headquarters, use first branch
      if (branches.length > 0) {
        const firstBranch = branches[0];
        setSelectedBranch(firstBranch);
        localStorage.setItem('current_branch', JSON.stringify(firstBranch));
        if (onBranchChange) {
          onBranchChange(firstBranch);
        }
      }
    }
  };

  const handleBranchSelect = async (branch) => {
    try {
      // Set branch in backend session
      await branchesAPI.setCurrent(branch.id);
      setSelectedBranch(branch);
      localStorage.setItem('current_branch', JSON.stringify(branch));
      setShowDropdown(false);
      if (onBranchChange) {
        onBranchChange(branch);
      }
      toast.success(`Switched to ${branch.name}`);
      // Reload page to apply branch filter to all views
      setTimeout(() => {
        window.location.reload();
      }, 500);
    } catch (error) {
      console.error('Error setting current branch:', error);
      // Still update locally even if backend call fails
      setSelectedBranch(branch);
      localStorage.setItem('current_branch', JSON.stringify(branch));
      setShowDropdown(false);
      toast.success(`Switched to ${branch.name}`);
      setTimeout(() => {
        window.location.reload();
      }, 500);
    }
  };

  const handleShowAll = async () => {
    try {
      // Clear branch in backend session
      await branchesAPI.clearCurrent();
      setSelectedBranch(null);
      localStorage.removeItem('current_branch');
      setShowDropdown(false);
      if (onBranchChange) {
        onBranchChange(null);
      }
      toast.success('Showing all branches');
      // Reload page to show all branches
      setTimeout(() => {
        window.location.reload();
      }, 500);
    } catch (error) {
      console.error('Error clearing current branch:', error);
      // Still update locally
      setSelectedBranch(null);
      localStorage.removeItem('current_branch');
      setShowDropdown(false);
      toast.success('Showing all branches');
      setTimeout(() => {
        window.location.reload();
      }, 500);
    }
  };

  // Don't render if branch support is disabled
  if (!branchSupportEnabled) {
    return null;
  }

  if (loading) {
    return <div className="branch-selector-loading">Loading...</div>;
  }

  const displayName = selectedBranch 
    ? selectedBranch.name 
    : branches.length === 0
      ? 'No Branches'
      : showAllOption 
        ? 'All Branches' 
        : 'Select Branch';

  return (
    <div className="branch-selector">
      <div 
        className="branch-selector-trigger"
        onClick={() => setShowDropdown(!showDropdown)}
      >
        <span className="branch-icon">🏢</span>
        <span className="branch-name">{displayName}</span>
        <span className="dropdown-arrow">▼</span>
      </div>
      {showDropdown && (
        <>
          <div 
            className="branch-selector-overlay"
            onClick={() => setShowDropdown(false)}
          />
          <div className="branch-selector-dropdown">
            {showAllOption && (
              <div 
                className={`branch-option ${!selectedBranch ? 'active' : ''}`}
                onClick={handleShowAll}
              >
                <span className="branch-option-icon">🌐</span>
                <span className="branch-option-name">All Branches</span>
                {!selectedBranch && <span className="check-icon">✓</span>}
              </div>
            )}
            {branches.length === 0 ? (
              <div className="branch-option no-branches">
                <span className="branch-option-icon">ℹ️</span>
                <div className="branch-option-details">
                  <span className="branch-option-name">No branches available</span>
                  <span className="branch-option-location">Add branches through module settings</span>
                </div>
              </div>
            ) : (
              branches.map(branch => (
                <div
                  key={branch.id}
                  className={`branch-option ${selectedBranch?.id === branch.id ? 'active' : ''}`}
                  onClick={() => handleBranchSelect(branch)}
                >
                  <span className="branch-option-icon">
                    {branch.is_headquarters ? '🏛️' : '🏢'}
                  </span>
                  <div className="branch-option-details">
                    <span className="branch-option-name">{branch.name}</span>
                    {branch.city && (
                      <span className="branch-option-location">{branch.city}</span>
                    )}
                  </div>
                  {selectedBranch?.id === branch.id && (
                    <span className="check-icon">✓</span>
                  )}
                </div>
              ))
            )}
          </div>
        </>
      )}
    </div>
  );
};

export default BranchSelector;
