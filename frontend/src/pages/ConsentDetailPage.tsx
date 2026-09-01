import { useCallback, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';

import { useConsent, useConsentHistory, useRevokeConsent } from '../api/consents';
import { LoadingSpinner } from '../components/common/LoadingSpinner';
import { ErrorAlert } from '../components/common/ErrorAlert';
import { PageHeader } from '../components/common/PageHeader';
import { ConfirmDialog } from '../components/common/ConfirmDialog';
import { ConsentDetail } from '../components/consents/ConsentDetail';

export function ConsentDetailPage() {
  const { consentId } = useParams<{ consentId: string }>();
  const navigate = useNavigate();
  const [revokeOpen, setRevokeOpen] = useState(false);

  const {
    data: consent,
    isLoading: consentLoading,
    error: consentError,
    refetch: refetchConsent,
  } = useConsent(consentId!);

  const {
    data: history,
    isLoading: historyLoading,
  } = useConsentHistory(consentId!);

  const revokeMutation = useRevokeConsent();

  const handleRevoke = useCallback(() => {
    setRevokeOpen(true);
  }, []);

  const handleConfirmRevoke = useCallback(() => {
    if (!consentId) return;
    revokeMutation.mutate(consentId, {
      onSuccess: () => {
        setRevokeOpen(false);
        navigate('/consents');
      },
    });
  }, [consentId, revokeMutation, navigate]);

  const handleCancelRevoke = useCallback(() => {
    setRevokeOpen(false);
  }, []);

  if (!consentId) {
    return (
      <ErrorAlert
        title="Invalid Request"
        message="No consent ID was provided."
      />
    );
  }

  if (consentLoading || historyLoading) {
    return <LoadingSpinner message="Loading consent details..." />;
  }

  if (consentError) {
    const is404 =
      consentError instanceof Error &&
      (consentError.message.includes('404') || consentError.message.includes('not found'));

    if (is404) {
      return (
        <Box>
          <PageHeader title="Consent Not Found" />
          <ErrorAlert
            title="Not Found"
            message={`Consent record with ID "${consentId}" could not be found.`}
            onRetry={() => navigate('/consents')}
          />
        </Box>
      );
    }

    return (
      <ErrorAlert
        title="Failed to load consent"
        message="Unable to fetch consent details. Please try again."
        onRetry={() => refetchConsent()}
      />
    );
  }

  if (!consent) {
    return (
      <Box>
        <PageHeader title="Consent Not Found" />
        <ErrorAlert
          title="Not Found"
          message={`Consent record with ID "${consentId}" could not be found.`}
          onRetry={() => navigate('/consents')}
        />
      </Box>
    );
  }

  return (
    <Box>
      <PageHeader
        title="Consent Details"
        subtitle={`Consent ID: ${consentId}`}
        action={
          <Button
            variant="outlined"
            startIcon={<ArrowBackIcon />}
            onClick={() => navigate('/consents')}
          >
            Back to Consents
          </Button>
        }
      />

      <ConsentDetail
        consent={consent}
        history={history}
        onRevoke={consent.status === 'GRANTED' ? handleRevoke : undefined}
      />

      <ConfirmDialog
        open={revokeOpen}
        title="Revoke Consent"
        message="Are you sure you want to revoke this consent? This action cannot be undone and will take effect immediately."
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
