import React from 'react';
import Grid from '@mui/material/Grid';

import { useConsentAnalytics } from '../../api/analytics';
import { useIncidents } from '../../api/incidents';
import { LoadingSpinner } from '../common/LoadingSpinner';
import { ErrorAlert } from '../common/ErrorAlert';
import KPICards from './KPICards';
import ConsentRateChart from './ConsentRateChart';
import ChannelDistribution from './ChannelDistribution';
import StatusBreakdown from './StatusBreakdown';

const AnalyticsDashboard: React.FC = () => {
  const {
    data: analytics,
    isLoading: analyticsLoading,
    error: analyticsError,
    refetch: refetchAnalytics,
  } = useConsentAnalytics();

  const {
    data: incidentsData,
    isLoading: incidentsLoading,
    error: incidentsError,
    refetch: refetchIncidents,
  } = useIncidents();

  const isLoading = analyticsLoading || incidentsLoading;
  const error = analyticsError || incidentsError;

  if (isLoading) {
    return <LoadingSpinner message="Loading analytics..." />;
  }

  if (error) {
    return (
      <ErrorAlert
        title="Failed to load analytics"
        message={
          error instanceof Error ? error.message : 'An unexpected error occurred'
        }
        onRetry={() => {
          refetchAnalytics();
          refetchIncidents();
        }}
      />
    );
  }

  const incidents = incidentsData?.items ?? [];
  const activeIncidents = incidents.filter(
    (incident) =>
      incident.status === 'OPEN' || incident.status === 'ACKNOWLEDGED'
  ).length;

  return (
    <Grid container spacing={3}>
      <Grid size={12}>
        <KPICards analytics={analytics} activeIncidents={activeIncidents} />
      </Grid>

      <Grid size={{ xs: 12, md: 8 }}>
        <ConsentRateChart data={analytics?.daily_counts} />
      </Grid>

      <Grid size={{ xs: 12, md: 4 }}>
        <ChannelDistribution data={analytics?.consents_by_channel} />
      </Grid>

      <Grid size={12}>
        <StatusBreakdown data={analytics?.consents_by_status} />
      </Grid>
    </Grid>
  );
};

export default AnalyticsDashboard;
