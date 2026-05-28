import React, { useState, useEffect } from 'react';
import { Building2, Check, ChevronDown, Globe, Loader2 } from 'lucide-react';
import { branchesAPI, modulesAPI } from '../../services/api';
import { toast } from '../../utils/toast';
import { Button } from '../ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '../ui/dropdown-menu';
import { cn } from '../../lib/cn';

const BranchSelector = ({ onBranchChange, showAllOption = false }) => {
  const [branches, setBranches] = useState([]);
  const [selectedBranch, setSelectedBranch] = useState(null);
  const [loading, setLoading] = useState(true);
  const [branchSupportEnabled, setBranchSupportEnabled] = useState(false);

  useEffect(() => {
    checkBranchSupport();
  }, []);

  useEffect(() => {
    if (branchSupportEnabled) {
      loadBranches();
    } else {
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
      setBranchSupportEnabled(multiBranchFeature?.is_enabled || false);
    } catch {
      setBranchSupportEnabled(false);
    }
  };

  useEffect(() => {
    if (branches.length > 0 && !selectedBranch) {
      loadCurrentBranch();
    }
  }, [branches]);

  const loadBranches = async () => {
    if (!branchSupportEnabled) {
      setBranches([]);
      setLoading(false);
      return;
    }
    try {
      const response = await branchesAPI.active();
      setBranches(response.data || []);
    } catch (error) {
      if (error.response?.status !== 404 && error.code !== 'ERR_NETWORK') {
        toast.error('Failed to load branches');
      }
      setBranches([]);
    } finally {
      setLoading(false);
    }
  };

  const loadCurrentBranch = async () => {
    const storedBranch = localStorage.getItem('current_branch');
    if (storedBranch) {
      try {
        const branch = JSON.parse(storedBranch);
        if (branches.find((b) => b.id === branch.id)) {
          setSelectedBranch(branch);
          onBranchChange?.(branch);
          return;
        }
      } catch {
        /* ignore */
      }
    }
    try {
      const hqResponse = await branchesAPI.headquarters();
      if (hqResponse.data) {
        setSelectedBranch(hqResponse.data);
        localStorage.setItem('current_branch', JSON.stringify(hqResponse.data));
        onBranchChange?.(hqResponse.data);
        return;
      }
    } catch {
      /* no HQ */
    }
    if (branches.length > 0) {
      const firstBranch = branches[0];
      setSelectedBranch(firstBranch);
      localStorage.setItem('current_branch', JSON.stringify(firstBranch));
      onBranchChange?.(firstBranch);
    }
  };

  const applyBranch = async (branch, clear = false) => {
    try {
      if (clear) {
        await branchesAPI.clearCurrent();
        setSelectedBranch(null);
        localStorage.removeItem('current_branch');
        onBranchChange?.(null);
        toast.success('Showing all branches');
      } else {
        await branchesAPI.setCurrent(branch.id);
        setSelectedBranch(branch);
        localStorage.setItem('current_branch', JSON.stringify(branch));
        onBranchChange?.(branch);
        toast.success(`Switched to ${branch.name}`);
      }
    } catch {
      if (clear) {
        setSelectedBranch(null);
        localStorage.removeItem('current_branch');
      } else {
        setSelectedBranch(branch);
        localStorage.setItem('current_branch', JSON.stringify(branch));
      }
      toast.success(clear ? 'Showing all branches' : `Switched to ${branch.name}`);
    }
    setTimeout(() => window.location.reload(), 400);
  };

  if (!branchSupportEnabled) return null;

  if (loading) {
    return (
      <Button variant="outline" size="sm" disabled className="h-9 gap-2">
        <Loader2 className="h-4 w-4 animate-spin" />
        <span className="hidden sm:inline">Branch</span>
      </Button>
    );
  }

  const displayName = selectedBranch
    ? selectedBranch.name
    : branches.length === 0
      ? 'No branches'
      : showAllOption
        ? 'All branches'
        : 'Select branch';

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="outline" size="sm" className="h-9 max-w-[180px] gap-2">
          <Building2 className="h-4 w-4 shrink-0 text-primary" />
          <span className="truncate">{displayName}</span>
          <ChevronDown className="h-4 w-4 shrink-0 opacity-50" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-56">
        <DropdownMenuLabel>Store location</DropdownMenuLabel>
        <DropdownMenuSeparator />
        {showAllOption && (
          <DropdownMenuItem onClick={() => applyBranch(null, true)}>
            <Globe className="h-4 w-4" />
            <span className="flex-1">All branches</span>
            {!selectedBranch && <Check className="h-4 w-4 text-primary" />}
          </DropdownMenuItem>
        )}
        {branches.length === 0 ? (
          <DropdownMenuItem disabled className="text-muted-foreground">
            No branches — add in settings
          </DropdownMenuItem>
        ) : (
          branches.map((branch) => (
            <DropdownMenuItem
              key={branch.id}
              onClick={() => applyBranch(branch)}
              className={cn(selectedBranch?.id === branch.id && 'bg-primary/5')}
            >
              <Building2 className="h-4 w-4" />
              <div className="flex min-w-0 flex-1 flex-col">
                <span className="truncate font-medium">{branch.name}</span>
                {branch.city && (
                  <span className="text-xs text-muted-foreground">{branch.city}</span>
                )}
              </div>
              {selectedBranch?.id === branch.id && (
                <Check className="h-4 w-4 text-primary" />
              )}
            </DropdownMenuItem>
          ))
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  );
};

export default BranchSelector;
