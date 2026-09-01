import { useState } from 'react';
import {
  Alert,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  MenuItem,
  RadioGroup,
  FormControlLabel,
  Radio,
  FormControl,
  FormLabel,
  TextField,
} from '@mui/material';
import type { ConsentChannel, ConsentType, CreateConsentRequest } from '../../api/types';
import { useCreateConsent } from '../../api/consents';
import { CONSENT_TYPES } from '../../utils/constants';

interface ConsentFormProps {
  open: boolean;
  onClose: () => void;
  onSuccess?: () => void;
}

interface FormState {
  customer_id: string;
  consent_type: ConsentType;
  channel: ConsentChannel;
  phone_number: string;
  email: string;
  consent_text: string;
  expiry_hours: string;
}

const INITIAL_STATE: FormState = {
  customer_id: '',
  consent_type: 'MARKETING',
  channel: 'SMS',
  phone_number: '',
  email: '',
  consent_text: '',
  expiry_hours: '',
};

export function ConsentForm({ open, onClose, onSuccess }: ConsentFormProps) {
  const [form, setForm] = useState<FormState>(INITIAL_STATE);
  const [error, setError] = useState<string | null>(null);

  const createConsent = useCreateConsent();

  const handleChange = (field: keyof FormState, value: string) => {
    setForm((prev) => ({ ...prev, [field]: value }));
    setError(null);
  };

  const handleSubmit = async () => {
    setError(null);

    if (!form.customer_id.trim()) {
      setError('Customer ID is required.');
      return;
    }
    if (!form.consent_text.trim()) {
      setError('Consent text is required.');
      return;
    }
    if (form.channel === 'SMS' && !form.phone_number.trim()) {
      setError('Phone number is required for SMS channel.');
      return;
    }
    if (form.channel === 'EMAIL' && !form.email.trim()) {
      setError('Email is required for EMAIL channel.');
      return;
    }

    const payload: CreateConsentRequest = {
      customer_id: form.customer_id.trim(),
      consent_type: form.consent_type,
      channel: form.channel,
      consent_text: form.consent_text.trim(),
    };

    if (form.channel === 'SMS') {
      payload.customer_phone = form.phone_number.trim();
    } else {
      payload.customer_email = form.email.trim();
    }

    if (form.expiry_hours.trim()) {
      const hours = Number(form.expiry_hours);
      if (!Number.isNaN(hours) && hours > 0) {
        payload.expiry_hours = hours;
      }
    }

    try {
      await createConsent.mutateAsync(payload);
      setForm(INITIAL_STATE);
      onSuccess?.();
      onClose();
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : 'Failed to create consent request.';
      setError(message);
    }
  };

  const handleClose = () => {
    setForm(INITIAL_STATE);
    setError(null);
    onClose();
  };

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="sm" fullWidth>
      <DialogTitle>Create Consent Request</DialogTitle>
      <DialogContent
        sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: '16px !important' }}
      >
        {error && (
          <Alert severity="error" onClose={() => setError(null)}>
            {error}
          </Alert>
        )}

        <TextField
          label="Customer ID"
          value={form.customer_id}
          onChange={(e) => handleChange('customer_id', e.target.value)}
          required
          fullWidth
        />

        <TextField
          label="Consent Type"
          value={form.consent_type}
          onChange={(e) => handleChange('consent_type', e.target.value)}
          select
          required
          fullWidth
        >
          {CONSENT_TYPES.map((type) => (
            <MenuItem key={type} value={type}>
              {type.replace(/_/g, ' ')}
            </MenuItem>
          ))}
        </TextField>

        <FormControl>
          <FormLabel>Channel</FormLabel>
          <RadioGroup
            row
            value={form.channel}
            onChange={(e) => handleChange('channel', e.target.value)}
          >
            <FormControlLabel value="SMS" control={<Radio />} label="SMS" />
            <FormControlLabel value="EMAIL" control={<Radio />} label="Email" />
          </RadioGroup>
        </FormControl>

        {form.channel === 'SMS' && (
          <TextField
            label="Phone Number"
            value={form.phone_number}
            onChange={(e) => handleChange('phone_number', e.target.value)}
            required
            fullWidth
            placeholder="+1234567890"
          />
        )}

        {form.channel === 'EMAIL' && (
          <TextField
            label="Email"
            type="email"
            value={form.email}
            onChange={(e) => handleChange('email', e.target.value)}
            required
            fullWidth
            placeholder="user@example.com"
          />
        )}

        <TextField
          label="Consent Text"
          value={form.consent_text}
          onChange={(e) => handleChange('consent_text', e.target.value)}
          required
          fullWidth
          multiline
          rows={3}
        />

        <TextField
          label="Expiry Hours"
          type="number"
          value={form.expiry_hours}
          onChange={(e) => handleChange('expiry_hours', e.target.value)}
          fullWidth
          placeholder="72"
          slotProps={{ htmlInput: { min: 1 } }}
        />
      </DialogContent>

      <DialogActions>
        <Button onClick={handleClose} disabled={createConsent.isPending}>
          Cancel
        </Button>
        <Button
          variant="contained"
          onClick={handleSubmit}
          disabled={createConsent.isPending}
        >
          {createConsent.isPending ? 'Submitting...' : 'Submit'}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
