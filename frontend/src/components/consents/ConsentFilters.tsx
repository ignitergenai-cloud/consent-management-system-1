import { Box, Button, InputAdornment, MenuItem, TextField } from '@mui/material';
import { Search as SearchIcon } from '@mui/icons-material';
import { CONSENT_STATUSES, CONSENT_CHANNELS } from '../../utils/constants';

export interface ConsentFiltersState {
  status?: string;
  channel?: string;
  customer_id?: string;
  start_date?: string;
  end_date?: string;
}

interface ConsentFiltersProps {
  filters: ConsentFiltersState;
  onFiltersChange: (filters: ConsentFiltersState) => void;
  onReset: () => void;
}

export function ConsentFilters({ filters, onFiltersChange, onReset }: ConsentFiltersProps) {
  const handleChange = (field: keyof ConsentFiltersState, value: string) => {
    onFiltersChange({ ...filters, [field]: value || undefined });
  };

  return (
    <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap', alignItems: 'center' }}>
      <TextField
        select
        label="Status"
        value={filters.status ?? ''}
        onChange={(e) => handleChange('status', e.target.value)}
        size="small"
        sx={{ minWidth: 160 }}
      >
        <MenuItem value="">All Statuses</MenuItem>
        {CONSENT_STATUSES.map((status) => (
          <MenuItem key={status} value={status}>
            {status}
          </MenuItem>
        ))}
      </TextField>

      <TextField
        select
        label="Channel"
        value={filters.channel ?? ''}
        onChange={(e) => handleChange('channel', e.target.value)}
        size="small"
        sx={{ minWidth: 150 }}
      >
        <MenuItem value="">All Channels</MenuItem>
        {CONSENT_CHANNELS.map((channel) => (
          <MenuItem key={channel} value={channel}>
            {channel}
          </MenuItem>
        ))}
      </TextField>

      <TextField
        label="Customer ID"
        value={filters.customer_id ?? ''}
        onChange={(e) => handleChange('customer_id', e.target.value)}
        size="small"
        placeholder="Search customer..."
        slotProps={{
          input: {
            startAdornment: (
              <InputAdornment position="start">
                <SearchIcon fontSize="small" />
              </InputAdornment>
            ),
          },
        }}
        sx={{ minWidth: 200 }}
      />

      <TextField
        label="From"
        type="date"
        value={filters.start_date ?? ''}
        onChange={(e) => handleChange('start_date', e.target.value)}
        size="small"
        slotProps={{ inputLabel: { shrink: true } }}
        sx={{ minWidth: 150 }}
      />

      <TextField
        label="To"
        type="date"
        value={filters.end_date ?? ''}
        onChange={(e) => handleChange('end_date', e.target.value)}
        size="small"
        slotProps={{ inputLabel: { shrink: true } }}
        sx={{ minWidth: 150 }}
      />

      <Button variant="outlined" onClick={onReset}>
        Reset
      </Button>
    </Box>
  );
}
