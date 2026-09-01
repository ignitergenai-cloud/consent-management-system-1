import React from 'react';
import Card from '@mui/material/Card';
import CardContent from '@mui/material/CardContent';
import Typography from '@mui/material/Typography';
import Chip from '@mui/material/Chip';
import Grid from '@mui/material/Grid';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Divider from '@mui/material/Divider';

import type { Incident, IncidentSeverity } from '../../api/types';
import { INCIDENT_SEVERITY_COLORS } from '../../utils/constants';
import { formatDateTime } from '../../utils/formatters';

interface IncidentDetailProps {
  incident: Incident;
  onAcknowledge: () => void;
  onResolve: () => void;
}

const IncidentDetail: React.FC<IncidentDetailProps> = ({
  incident,
  onAcknowledge,
  onResolve,
}) => {
  const showAcknowledge = incident.status === 'OPEN';
  const showResolve =
    incident.status !== 'RESOLVED' && incident.status !== 'CLOSED';

  return (
    <Card>
      <CardContent>
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            mb: 2,
          }}
        >
          <Typography variant="h5" component="h2">
            {incident.title}
          </Typography>
          <Chip
            label={incident.severity}
            sx={{
              bgcolor:
                INCIDENT_SEVERITY_COLORS[
                  incident.severity as IncidentSeverity
                ] ?? '#9e9e9e',
              color: '#fff',
              fontWeight: 'bold',
            }}
          />
        </Box>

        <Typography variant="body1" sx={{ mb: 3 }}>
          {incident.description}
        </Typography>

        <Divider sx={{ mb: 3 }} />

        <Grid container spacing={3} sx={{ mb: 3 }}>
          <Grid size={{ xs: 12, sm: 6, md: 4 }}>
            <Typography variant="caption" color="text.secondary">
              Type
            </Typography>
            <Typography variant="body1">
              {incident.type
                .replace(/_/g, ' ')
                .toLowerCase()
                .replace(/\b\w/g, (char) => char.toUpperCase())}
            </Typography>
          </Grid>

          <Grid size={{ xs: 12, sm: 6, md: 4 }}>
            <Typography variant="caption" color="text.secondary">
              Status
            </Typography>
            <Box>
              <Chip label={incident.status} size="small" />
            </Box>
          </Grid>

          <Grid size={{ xs: 12, sm: 6, md: 4 }}>
            <Typography variant="caption" color="text.secondary">
              Detected At
            </Typography>
            <Typography variant="body1">
              {formatDateTime(incident.detected_at)}
            </Typography>
          </Grid>

          <Grid size={{ xs: 12, sm: 6, md: 4 }}>
            <Typography variant="caption" color="text.secondary">
              Acknowledged At
            </Typography>
            <Typography variant="body1">
              {incident.acknowledged_at
                ? formatDateTime(incident.acknowledged_at)
                : '—'}
            </Typography>
          </Grid>

          <Grid size={{ xs: 12, sm: 6, md: 4 }}>
            <Typography variant="caption" color="text.secondary">
              Resolved At
            </Typography>
            <Typography variant="body1">
              {incident.resolved_at
                ? formatDateTime(incident.resolved_at)
                : '—'}
            </Typography>
          </Grid>

          <Grid size={{ xs: 12, sm: 6, md: 4 }}>
            <Typography variant="caption" color="text.secondary">
              Affected Customers
            </Typography>
            <Typography variant="body1">
              {incident.affected_customers}
            </Typography>
          </Grid>
        </Grid>

        {(showAcknowledge || showResolve) && (
          <>
            <Divider sx={{ mb: 2 }} />
            <Box sx={{ display: 'flex', gap: 2, justifyContent: 'flex-end' }}>
              {showAcknowledge && (
                <Button
                  variant="outlined"
                  color="warning"
                  onClick={onAcknowledge}
                >
                  Acknowledge
                </Button>
              )}
              {showResolve && (
                <Button
                  variant="contained"
                  color="success"
                  onClick={onResolve}
                >
                  Resolve
                </Button>
              )}
            </Box>
          </>
        )}
      </CardContent>
    </Card>
  );
};

export default IncidentDetail;
