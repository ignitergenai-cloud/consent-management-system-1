import { useState, useCallback, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import AddIcon from '@mui/icons-material/Add';

import { useConsents, useRevokeConsent } from '../api/consents';
import { ErrorAlert } from '../components/common/ErrorAlert';
import { PageHeader } from '../components/common/PageHeader';
import { ConfirmDialog } from '../components/common/ConfirmDialog';
import { ConsentTable } from '../components/consents/ConsentTable';
import { ConsentFilters } from '../components/consents/ConsentFilters';
import { ConsentForm } from '../components/consents/ConsentForm';

interface ConsentFiltersState {
  status?: string;
  channel?: string;
  customer_id?: string;
  start_date?: string;
  end_date?: string;
}

export function ConsentsPage() {
  const navigate = useNavigate();
  const location = useLocation();

  const [filters, setFilters] = useState<ConsentFiltersState>({});
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(25);
  const [formOpen, setFormOpen] = useState(false);
  const [revokeId, setRevokeId] = useState<string | null>(null);

  // Open form if navigated here with state.openForm
  useEffect(() => {
    if (location.state?.openForm) {
      setFormOpen(true);
      // Clear the state so it doesn't re-trigger on re-renders
      window.history.replaceState({}, document.title);
    }
  }, [location.state]);

  const {
    data: consentsData,
    isLoading,
    error,
    refetch,
  } = useConsents({
    page: page + 1,
    page_size: pageSize,
    ...filters,
  });

  const revokeMutation = useRevokeConsent();

  const consents = consentsData?.items ?? [];
  const total = consentsData?.count ?? 0;

  const handleView = useCallback(
    (id: string) => {
      navigate(`/consents/${id}`);
    },
    [navigate],
  );

  const handleRevoke = useCallback((id: string) => {
    setRevokeId(id);
  }, []);

  const handleConfirmRevoke = useCallback(() => {
    if (!revokeId) return;
    revokeMutation.mutate(revokeId, {
      onSuccess: () => {
        setRevokeId(null);
        refetch();
      },
    });
  }, [revokeId, revokeMutation, refetch]);

  const handleCancelRevoke = useCallback(() => {
    setRevokeId(null);
  }, []);

  const handlePageChange = useCallback((newPage: number) => {
    setPage(newPage);
  }, []);

  const handlePageSizeChange = useCallback((newPageSize: number) => {
    setPageSize(newPageSize);
    setPage(0);
  }, []);

  const handleFiltersChange = useCallback((newFilters: ConsentFiltersState) => {
    setFilters(newFilters);
    setPage(0);
  }, []);

  const handleFiltersReset = useCallback(() => {
    setFilters({});
    setPage(0);
  }, []);

  const handleFormSuccess = useCallback(() => {
    setFormOpen(false);
    refetch();
  }, [refetch]);

  return (
    <Box>
      <PageHeader
        title="Consents"
        subtitle="Manage consent records"
        action={
          <Button
            variant="contained"
            startIcon={<AddIcon />}
            onClick={() => setFormOpen(true)}
          >
            Create Consent
          </Button>
        }
      />

      <Box sx={{ mb: 3 }}>
        <ConsentFilters
          filters={filters}
          onFiltersChange={handleFiltersChange}
          onReset={handleFiltersReset}
        />
      </Box>

      {error ? (
        <ErrorAlert
          title="Failed to load consents"
          message="Unable to fetch consent records. Please try again."
          onRetry={() => refetch()}
        />
      ) : (
        <ConsentTable
          consents={consents}
          loading={isLoading}
          total={total}
          page={page}
          pageSize={pageSize}
          onPageChange={handlePageChange}
          onPageSizeChange={handlePageSizeChange}
          onView={handleView}
          onRevoke={handleRevoke}
        />
      )}

      <ConsentForm
        open={formOpen}
        onClose={() => setFormOpen(false)}
        onSuccess={handleFormSuccess}
      />

      <ConfirmDialog
        open={revokeId !== null}
        title="Revoke Consent"
        message="Are you sure you want to revoke this consent? This action cannot be undone."
        confirmLabel="Revoke"
        cancelLabel="Cancel"
        confirmColor="error"
        onConfirm={handleConfirmRevoke}
        onCancel={handleCancelRevoke}
        loading={revokeMutation.isPending}
      />
    </Box>
  );
}
