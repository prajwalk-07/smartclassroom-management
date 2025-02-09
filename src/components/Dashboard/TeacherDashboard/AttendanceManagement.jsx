import React, { useState, useEffect } from "react";
import {
  Box,
  Paper,
  Typography,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Button,
  TextField,
  MenuItem,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Alert,
  CircularProgress,
  Chip,
} from "@mui/material";
import { DatePicker } from "@mui/x-date-pickers";
import axios from "axios";

const AttendanceManagement = () => {
  const [attendanceRequests, setAttendanceRequests] = useState([]);
  const [selectedDate, setSelectedDate] = useState(new Date());
  const [selectedStudent, setSelectedStudent] = useState("");
  const [students, setStudents] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [showLogsDialog, setShowLogsDialog] = useState(false);
  const [selectedLogs, setSelectedLogs] = useState([]);
  const [monitoringLogs, setMonitoringLogs] = useState([]);

  useEffect(() => {
    fetchAttendanceRequests();
    fetchStudents();
  }, [selectedDate]);
  const getTeacherInfo = () => {
    const userStr = localStorage.getItem("user"); // Change from sessionStorage to localStorage
    if (!userStr) {
      setError("Please log in again");
      return null;
    }
    const userData = JSON.parse(userStr);
    if (!userData.role_id) {
      setError("Teacher information not found");
      return null;
    }
    return userData;
  };
  // ... existing code ...
  const fetchAttendanceRequests = async () => {
    try {
      setLoading(true);
      setError("");

      // Get teacher data from localStorage
      const userData = JSON.parse(localStorage.getItem("user"));
      if (!userData || !userData.role_id) {
        throw new Error("Teacher information not found");
      }

      const response = await axios.get(
        "http://localhost:5000/teacher/attendance-requests",
        {
          params: {
            teacher_id: userData.role_id,
            date: selectedDate.toISOString().split("T")[0],
          },
        }
      );

      if (response.data.status === "success") {
        setAttendanceRequests(response.data.data);
      } else {
        throw new Error(
          response.data.message || "Failed to fetch attendance requests"
        );
      }
    } catch (error) {
      console.error("Error:", error);
      setError(
        error.response?.data?.message || "Failed to fetch attendance requests"
      );
    } finally {
      setLoading(false);
    }
  };

  const fetchStudents = async () => {
    try {
      const user = getTeacherInfo();
      if (!user) return;

      const response = await axios.get(
        `http://localhost:5000/teacher/students`,
        {
          params: {
            user_id: user.id,
          },
        }
      );

      if (response.data.status === "success") {
        setStudents(response.data.data);
      } else {
        console.error("Failed to fetch students:", response.data.message);
        setError("Failed to fetch students");
      }
    } catch (error) {
      console.error("Error fetching students:", error);
      setError(
        "Error fetching students: " +
          (error.response?.data?.message || error.message)
      );
    }
  };
  const handleMarkAttendance = async (studentId, subjectId, type) => {
    try {
      const userData = sessionStorage.getItem("userData");
      if (!userData) {
        setError("Please log in again");
        return;
      }
      const user = JSON.parse(userData);
      const response = await axios.post(
        "http://localhost:5000/teacher/mark-attendance",
        {
          student_id: studentId,
          subject_id: subjectId,
          type: type,
          user_id: user.id,
        }
      );
      if (response.data.status === "success") {
        setSuccess(response.data.message);
        fetchAttendanceRequests();
      }
    } catch (error) {
      setError(error.response?.data?.message || "Failed to mark attendance");
    }
  };
  const handleViewLogs = async (studentId, subjectId) => {
    try {
        const user = getTeacherInfo();
        if (!user) return;

        const response = await axios.get(
            "http://localhost:5000/teacher/monitoring-logs",
            {
                params: {
                    student_id: studentId,
                    subject_id: subjectId,
                    date: selectedDate.toISOString().split('T')[0],
                    teacher_id: user.role_id  // Add this line
                },
            }
        );

        if (response.data.status === "success") {
            setSelectedLogs(response.data.data);
            setShowLogsDialog(true);
        }
    } catch (error) {
        console.error("Error fetching logs:", error);
        setError("Failed to fetch monitoring logs");
    }
};

  const handleResponse = async (requestId, newStatus) => {
    try {
      const user = JSON.parse(localStorage.getItem("user"));
      if (!user || !user.role_id) {
        setError("User information not found");
        return;
      }

      const response = await axios.post(
        "http://localhost:5000/teacher/respond-attendance",
        {
          request_id: requestId,
          status: newStatus,
          teacher_id: user.role_id,
        }
      );

      if (response.data.status === "success") {
        setSuccess(`Attendance request ${newStatus} successfully`);
        // Refresh the attendance requests
        fetchAttendanceRequests();
      }
    } catch (error) {
      setError(
        error.response?.data?.message || `Failed to ${newStatus} request`
      );
    }
  };
  const LogsDialog = ({ open, onClose, logs }) => {
    return (
      <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
        <DialogTitle>Monitoring Logs</DialogTitle>
        <DialogContent>
          {logs.length > 0 ? (
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell>Time</TableCell>
                  <TableCell>Status</TableCell>
                  <TableCell>Student</TableCell>
                  <TableCell>Subject</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {logs.map((log) => (
                  <TableRow key={log.id}>
                    <TableCell>
                      {new Date(log.timestamp).toLocaleString()}
                    </TableCell>
                    <TableCell>{log.status}</TableCell>
                    <TableCell>{log.student_name}</TableCell>
                    <TableCell>{log.subject_name}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <Typography>No monitoring logs found</Typography>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={onClose}>Close</Button>
        </DialogActions>
      </Dialog>
    );
  };
  return (
    <Box>
      <Typography variant="h5" gutterBottom>
        Attendance Management
      </Typography>

      <Box sx={{ mb: 3, display: "flex", gap: 2 }}>
        <DatePicker
          label="Select Date"
          value={selectedDate}
          onChange={setSelectedDate}
        />
        <TextField
          select
          label="Filter by Student"
          value={selectedStudent}
          onChange={(e) => setSelectedStudent(e.target.value)}
          sx={{ minWidth: 200 }}
        >
          <MenuItem value="">All Students</MenuItem>
          {students.map((student) => (
            <MenuItem key={student.id} value={student.id}>
              {student.name}
            </MenuItem>
          ))}
        </TextField>
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}
      {success && (
        <Alert severity="success" sx={{ mb: 2 }}>
          {success}
        </Alert>
      )}

      {loading ? (
        <CircularProgress />
      ) : (
        <TableContainer component={Paper}>
          <Table>
            <TableHead>
              <TableRow>
                <TableCell>Student Name</TableCell>
                <TableCell>Subject</TableCell>
                <TableCell>Request Time</TableCell>
                <TableCell>Status</TableCell>
                <TableCell>Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {attendanceRequests.map((request) => (
                <TableRow key={request.id}>
                  <TableCell>{request.student_name}</TableCell>
                  <TableCell>{request.subject_name}</TableCell>
                  <TableCell>
                    {request.request_time}
                  </TableCell>
                  <TableCell>
                    <Chip
                      label={request.status.toUpperCase()}
                      color={
                        request.status === "approved"
                          ? "success"
                          : request.status === "rejected"
                          ? "error"
                          : "warning"
                      }
                      size="small"
                    />
                  </TableCell>
                  <TableCell>
                    <Button
                      variant="outlined"
                      size="small"
                      onClick={() =>
                        handleViewLogs(request.student_id, request.subject_id)
                      }
                      sx={{ mr: 1 }}
                    >
                      View Logs
                    </Button>
                    {request.status === "pending" && (
                      <>
                        <Button
                          variant="contained"
                          color="success"
                          size="small"
                          onClick={() => handleResponse(request.id, "approved")}
                          sx={{ mr: 1 }}
                        >
                          Approve
                        </Button>
                        <Button
                          variant="contained"
                          color="error"
                          size="small"
                          onClick={() => handleResponse(request.id, "rejected")}
                        >
                          Reject
                        </Button>
                      </>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      )}

      <Dialog
        open={showLogsDialog}
        onClose={() => setShowLogsDialog(false)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>Student Monitoring Logs</DialogTitle>
        <DialogContent>
          <Box sx={{ width: "100%" }}>
            {selectedLogs.length === 0 ? (
              <Typography color="text.secondary">
                No monitoring logs found for this date
              </Typography>
            ) : (
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Time</TableCell>
                    <TableCell>Status</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {selectedLogs.map((log) => (
                    <TableRow key={log.id}>
                      <TableCell>{log.timestamp}</TableCell>
                      <TableCell>
                        <Chip
                          label={log.status_display}
                          color={
                            log.status === "active"
                              ? "success"
                              : log.status === "inactive"
                              ? "warning"
                              : "error"
                          }
                          size="small"
                        />
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setShowLogsDialog(false)}>Close</Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default AttendanceManagement;
