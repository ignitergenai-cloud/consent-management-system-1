import { IconButton, Tooltip, Box, Typography } from '@mui/material';
import { DataGrid, type GridColDef } from '@mui/x-data-grid';
import { Visibility, Delete, Sms as SmsIcon, Email as EmailIcon } from '@mui/icons-material';
import type { ConsentRecord } from '../../api/types';
import { formatDateTime, truncateId } from '../../utils/formatters';
import { ConsentStatusChip } from './ConsentStatusChip';

interface ConsentTableProps {
  consents: ConsentRecord[];
  loading: boolean;
  total: number;
  page: number;
  pageSize: number;
  onPageChange: (page: number) => void;
  onPageSizeChange: (pageSize: number) => void;
  onView: (id: string) => void;
  onRevoke: (id: string) => void;
}

export function ConsentTable({
  consents,
  loading,
  total,
  page,
  pageSize,
  onPageChange,
  onPageSizeChange,
  onView,
  onRevoke,
}: ConsentTableProps) {
  const columns: GridColDef<ConsentRecord>[] = [
    {
      field: 'id',
      headerName: 'ID',
      width: 130,
      renderCell: (params) => (
        <Tooltip title={params.row.consent_id}>
          <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
            {truncateId(params.row.consent_id)}
          </Typography>
        </Tooltip>
      ),
    },
    {
      field: 'customer_id',
      headerName: 'Customer ID',
      width: 150,
    },
    {
      field: 'consent_type',
      headerName: 'Type',
      width: 150,
    },
    {
      field: 'channel',
      headerName: 'Channel',
      width: 100,
      renderCell: (params) => (
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
          {params.row.channel === 'SMS' ? (
            <SmsIcon fontSize="small" color="action" />
          ) : (
            <EmailIcon fontSize="small" color="action" />
          )}
          {params.row.channel}
        </Box>
      ),
    },
    {
      field: 'status',
      headerName: 'Status',
      width: 130,
      renderCell: (params) => <ConsentStatusChip status={params.row.status} />,
    },
    {
      field: 'created_at',
      headerName: 'Created At',
      width: 170,
      valueFormatter: (value: string) => formatDateTime(value),
    },
    {
      field: 'expires_at',
      headerName: 'Expires At',
      width: 170,
      valueFormatter: (value: string | undefined | null) =>
        value ? formatDateTime(value) : 'N/A',
    },
    {
      field: 'actions',
      headerName: 'Actions',
      width: 150,
      sortable: false,
      filterable: false,
      disableColumnMenu: true,
      renderCell: (params) => (
        <Box>
          <Tooltip title="View details">
            <IconButton size="small" onClick={() => onView(params.row.consent_id)}>
              <Visibility fontSize="small" />
            </IconButton>
          </Tooltip>
          {(params.row.status === 'GRANTED' || params.row.status === 'PENDING') && (
            <Tooltip title="Revoke consent">
              <IconButton
                size="small"
                color="error"
                onClick={() => onRevoke(params.row.consent_id)}
              >
                <Delete fontSize="small" />
              </IconButton>
            </Tooltip>
          )}
        </Box>
      ),
    },
  ];

  return (
    <DataGrid
      rows={consents}
      columns={columns}
      loading={loading}
      rowCount={total}
      paginationMode="server"
      paginationModel={{ page, pageSize }}
      onPaginationModelChange={(model) => {
        if (model.page !== page) {
          onPageChange(model.page);
        }
        if (model.pageSize !== pageSize) {
          onPageSizeChange(model.pageSize);
        }
      }}
      pageSizeOptions={[10, 25, 50]}
      getRowId={(row) => row.consent_id}
      disableRowSelectionOnClick
      autoHeight
      sx={{ border: 'none' }}
    />
  );
}
