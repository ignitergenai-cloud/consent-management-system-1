import { useCallback } from 'react';
import Box from '@mui/material/Box';

import {
  useIncidents,
  useAcknowledgeIncident,
  useResolveIncident,
} from '../api/incidents';
import { LoadingSpinner } from '../components/common/LoadingSpinner';
import { ErrorAlert } from '../components/common/ErrorAlert';
import { PageHeader } from '../components/common/PageHeader';
import IncidentBanner from '../components/incidents/IncidentBanner';
import IncidentList from '../components/incidents/IncidentList';

export function IncidentsPage() {
  const {
    data: incidents,
    isLoading,
    error,
    refetch,
  } = useIncidents();

  const acknowledgeMutation = useAcknowledgeIncident();
  const resolveMutation = useResolveIncident();

  const handleAcknowledge = useCallback(
    (id: string) => {
      acknowledgeMutation.mutate(id, {
        onSuccess: () => refetch(),
      });
    },
    [acknowledgeMutation, refetch],
  );

  const handleResolve = useCallback(
    (id: string) => {
      resolveMutation.mutate({ id }, {
        onSuccess: () => refetch(),
      });
    },
    [resolveMutation, refetch],
  );

  if (isLoading) {
    return <LoadingSpinner message="Loading incidents..." />;
  }

  if (error) {
    return (
      <ErrorAlert
        title="Failed to load incidents"
        message="Unable to fetch incident data. Please try again."
        onRetry={() => refetch()}
      />
    );
  }

  const allIncidents = incidents?.items ?? [];
  const activeIncidents = allIncidents.filter((i) => i.status !== 'RESOLVED');

  return (
    <Box>
      <PageHeader
        title="Incidents"
        subtitle="Monitor and manage system incidents"
      />

      {activeIncidents.length > 0 && (
        <Box sx={{ mb: 3 }}>
          <IncidentBanner incidents={activeIncidents} />
        </Box>
      )}

      <IncidentList
        incidents={allIncidents}
        onAcknowledge={handleAcknowledge}
        onResolve={handleResolve}
      />
    </Box>
  );
}
