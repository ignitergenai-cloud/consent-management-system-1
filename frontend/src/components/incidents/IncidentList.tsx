import React from 'react';
import Table from '@mui/material/Table';
import TableBody from '@mui/material/TableBody';
import TableCell from '@mui/material/TableCell';
import TableContainer from '@mui/material/TableContainer';
import TableHead from '@mui/material/TableHead';
import TableRow from '@mui/material/TableRow';
import Paper from '@mui/material/Paper';
import Chip from '@mui/material/Chip';
import Button from '@mui/material/Button';
import Box from '@mui/material/Box';
import WarningIcon from '@mui/icons-material/Warning';

import type { Incident, IncidentSeverity } from '../../api/types';
import { INCIDENT_SEVERITY_COLORS } from '../../utils/constants';
import { formatDateTime } from '../../utils/formatters';
import { EmptyState } from '../common/EmptyState';

interface IncidentListProps {
  incidents: Incident[];
  onAcknowledge: (id: string) => void;
  onResolve: (id: string) => void;
}

function formatIncidentType(type: string): string {
  return type
    .replace(/_/g, ' ')
    .toLowerCase()
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

const IncidentList: React.FC<IncidentListProps> = ({
  incidents,
  onAcknowledge,
  onResolve,
}) => {
  if (incidents.length === 0) {
    return (
      <EmptyState
        icon={<WarningIcon />}
        title="No Incidents"
        description="No incidents have been recorded."
      />
    );
  }

  return (
    <TableContainer component={Paper}>
      <Table>
        <TableHead>
          <TableRow>
            <TableCell>Severity</TableCell>
            <TableCell>Title</TableCell>
            <TableCell>Type</TableCell>
            <TableCell>Status</TableCell>
            <TableCell>Detected At</TableCell>
            <TableCell>Affected</TableCell>
            <TableCell>Actions</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {incidents.map((incident) => (
            <TableRow key={incident.id}>
              <TableCell>
                <Chip
                  label={incident.severity}
                  size="small"
                  sx={{
                    bgcolor:
                      INCIDENT_SEVERITY_COLORS[
                        incident.severity as IncidentSeverity
                      ] ?? '#9e9e9e',
                    color: '#fff',
                    fontWeight: 'bold',
                  }}
                />
              </TableCell>
              <TableCell>{incident.title}</TableCell>
              <TableCell>{formatIncidentType(incident.type)}</TableCell>
              <TableCell>
                <Chip label={incident.status} size="small" />
              </TableCell>
              <TableCell>{formatDateTime(incident.detected_at)}</TableCell>
              <TableCell>{incident.affected_customers}</TableCell>
              <TableCell>
                <Box sx={{ display: 'flex', gap: 1 }}>
                  {incident.status === 'OPEN' && (
                    <Button
                      size="small"
                      variant="outlined"
                      color="warning"
                      onClick={() => onAcknowledge(incident.id)}
                    >
                      Acknowledge
                    </Button>
                  )}
                  {(incident.status === 'OPEN' ||
                    incident.status === 'ACKNOWLEDGED' ||
                    incident.status === 'INVESTIGATING') && (
                    <Button
                      size="small"
                      variant="outlined"
                      color="success"
                      onClick={() => onResolve(incident.id)}
                    >
                      Resolve
                    </Button>
                  )}
                </Box>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  );
};

export default IncidentList;
