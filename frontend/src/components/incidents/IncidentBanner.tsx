import React from 'react';
import Alert from '@mui/material/Alert';
import WarningIcon from '@mui/icons-material/Warning';

import type { Incident } from '../../api/types';

interface IncidentBannerProps {
  incidents: Incident[];
}

const IncidentBanner: React.FC<IncidentBannerProps> = ({ incidents }) => {
  const criticalIncidents = incidents.filter(
    (incident) =>
      (incident.severity === 'HIGH' || incident.severity === 'CRITICAL') &&
      (incident.status === 'OPEN' || incident.status === 'ACKNOWLEDGED')
  );

  if (criticalIncidents.length === 0) {
    return null;
  }

  if (criticalIncidents.length === 1) {
    const incident = criticalIncidents[0]!;
    return (
      <Alert severity="error" icon={<WarningIcon />} sx={{ mb: 2 }}>
        Active Incident: {incident.title} &mdash; {incident.affected_customers}{' '}
        customers affected
      </Alert>
    );
  }

  return (
    <Alert severity="error" icon={<WarningIcon />} sx={{ mb: 2 }}>
      {criticalIncidents.length} active critical incidents
    </Alert>
  );
};

export default IncidentBanner;
