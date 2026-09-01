import {
  Box,
  Button,
  Card,
  CardContent,
  Divider,
  List,
  ListItem,
  ListItemText,
  Typography,
} from '@mui/material';
import { ArrowForward } from '@mui/icons-material';
import type { ConsentRecord, ConsentHistoryEntry } from '../../api/types';
import { formatDateTime } from '../../utils/formatters';
import { ConsentStatusChip } from './ConsentStatusChip';

interface ConsentDetailProps {
  consent: ConsentRecord;
  history?: ConsentHistoryEntry[];
  onRevoke?: () => void;
}

export function ConsentDetail({ consent, history, onRevoke }: ConsentDetailProps) {
  const canRevoke = consent.status === 'GRANTED' || consent.status === 'PENDING';

  return (
    <Box>
      <Card>
        <CardContent>
          <Box
            sx={{
              display: 'grid',
              gridTemplateColumns: { xs: '1fr', md: '1fr 1fr' },
              gap: 3,
            }}
          >
            {/* Left column */}
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
              <DetailField label="ID" value={consent.consent_id} mono />
              <DetailField label="Customer ID" value={consent.customer_id} mono />
              <DetailField label="Consent Type" value={consent.consent_type} />
              <DetailField label="Channel" value={consent.channel} />
              <DetailField
                label={consent.channel === 'SMS' ? 'Phone Number' : 'Email'}
                value={consent.channel === 'SMS' ? consent.customer_phone : consent.customer_email}
              />
            </Box>

            {/* Right column */}
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
              <Box>
                <Typography variant="caption" color="text.secondary">
                  Status
                </Typography>
                <Box sx={{ mt: 0.5 }}>
                  <ConsentStatusChip status={consent.status} />
                </Box>
              </Box>
              <DetailField label="Created" value={formatDateTime(consent.created_at)} />
              <DetailField label="Updated" value={formatDateTime(consent.updated_at)} />
              <DetailField
                label="Expires"
                value={consent.expires_at ? formatDateTime(consent.expires_at) : 'N/A'}
              />
              <Box>
                <Typography variant="caption" color="text.secondary">
                  Consent Text
                </Typography>
                <Typography variant="body2" sx={{ mt: 0.5, whiteSpace: 'pre-wrap' }}>
                  {consent.consent_text}
                </Typography>
              </Box>
            </Box>
          </Box>

          {canRevoke && onRevoke && (
            <Box sx={{ mt: 3, display: 'flex', justifyContent: 'flex-end' }}>
              <Button variant="contained" color="error" onClick={onRevoke}>
                Revoke Consent
              </Button>
            </Box>
          )}
        </CardContent>
      </Card>

      {/* Status History */}
      {history && history.length > 0 && (
        <Box sx={{ mt: 4 }}>
          <Typography variant="h6" gutterBottom>
            Status History
          </Typography>
          <Card>
            <List disablePadding>
              {history.map((entry, index) => (
                <Box key={entry.id}>
                  {index > 0 && <Divider />}
                  <ListItem>
                    <ListItemText
                      primary={
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                          <ConsentStatusChip status={entry.previous_status} />
                          <ArrowForward fontSize="small" color="action" />
                          <ConsentStatusChip status={entry.new_status} />
                        </Box>
                      }
                      secondary={
                        <Box component="span" sx={{ display: 'block', mt: 0.5 }}>
                          <Typography variant="caption" color="text.secondary">
                            {formatDateTime(entry.changed_at)}
                          </Typography>
                          {entry.changed_by && (
                            <Typography variant="caption" color="text.secondary">
                              {' '}
                              &middot; by {entry.changed_by}
                            </Typography>
                          )}
                          {entry.reason && (
                            <Typography
                              variant="body2"
                              color="text.secondary"
                              sx={{ mt: 0.5 }}
                            >
                              {entry.reason}
                            </Typography>
                          )}
                        </Box>
                      }
                    />
                  </ListItem>
                </Box>
              ))}
            </List>
          </Card>
        </Box>
      )}
    </Box>
  );
}

function DetailField({
  label,
  value,
  mono = false,
}: {
  label: string;
  value?: string | null;
  mono?: boolean;
}) {
  return (
    <Box>
      <Typography variant="caption" color="text.secondary">
        {label}
      </Typography>
      <Typography
        variant="body2"
        sx={mono ? { fontFamily: 'monospace', wordBreak: 'break-all' } : undefined}
      >
        {value || 'N/A'}
      </Typography>
    </Box>
  );
}
