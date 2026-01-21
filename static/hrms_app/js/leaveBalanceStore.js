class LeaveBalanceStore {
    constructor() {
        // Initial State
        this.state = {
            leaveTypes: [],
            selectedLeaveType: null,
            users: [],
            leaveBalances: [],
            previewData: null,
            filteredPreviewData: [],
            loading: {
                leaveTypes: false,
                users: false,
                leaveBalances: false,
                preview: false,
                execute: false,
            },
            error: null,
            success: null,
            previewFilter: 'all',
            selectedYear: new Date().getFullYear(),
            selectedUserIds: [],
            pagination: {
                leaveTypes: { count: 0, next: null, previous: null },
                users: { count: 0, next: null, previous: null },
                leaveBalances: { count: 0, next: null, previous: null },
            },
        };

        this.listeners = [];
    }

    // Subscribe to state changes
    subscribe(listener) {
        this.listeners.push(listener);
        return () => {
            this.listeners = this.listeners.filter(l => l !== listener);
        };
    }

    // Notify all listeners of state change
    notify() {
        this.listeners.forEach(listener => listener(this.state));
    }

    // Update state
    setState(updates) {
        this.state = { ...this.state, ...updates };
        this.notify();
    }

    // Get current state
    getState() {
        return this.state;
    }

    // ==================== API Helper ====================
    async apiCall(url, options = {}) {
        try {
            const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value;
            const headers = {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken,
                ...options.headers,
            };

            const response = await fetch(url, {
                ...options,
                headers,
            });

            const data = await response.json();
            
            if (!response.ok) {
                throw new Error(data.message || 'Request failed');
            }

            return { data, success: true };
        } catch (error) {
            return { error: error.message, success: false };
        }
    }

    // ==================== Fetchers ====================
    async fetchLeaveTypes(filters = {}) {
        this.setState({
            loading: { ...this.state.loading, leaveTypes: true },
            error: null,
        });

        const params = new URLSearchParams(filters);
        const url = `/api/v1/leavetype/?${params}`;
        
        const response = await this.apiCall(url);
        if (response.success) {
            this.setState({
                leaveTypes: response.data.data || [],
                loading: { ...this.state.loading, leaveTypes: false },
            });
        } else {
            this.setState({
                error: response.error || 'Failed to fetch leave types',
                loading: { ...this.state.loading, leaveTypes: false },
            });
        }
    }

    async fetchUsers(filters = { is_active: true }) {
        this.setState({
            loading: { ...this.state.loading, users: true },
            error: null,
        });

        const params = new URLSearchParams(filters);
        const url = `/api/v1/user/?${params}`;
        
        const response = await this.apiCall(url);

        if (response.success) {
            this.setState({
                users: response.data.results || [],
                pagination: {
                    ...this.state.pagination,
                    users: {
                        count: response.data.count || 0,
                        next: response.data.next || null,
                        previous: response.data.previous || null,
                    },
                },
                loading: { ...this.state.loading, users: false },
            });
        } else {
            this.setState({
                error: response.error || 'Failed to fetch users',
                loading: { ...this.state.loading, users: false },
            });
        }
    }

    async fetchLeaveBalances(filters = {}) {
        this.setState({
            loading: { ...this.state.loading, leaveBalances: true },
            error: null,
        });

        const params = new URLSearchParams(filters);
        const url = `/api/v1/leave-openings?${params}`;
        
        const response = await this.apiCall(url);

        if (response.success) {
            this.setState({
                leaveBalances: response.data.results || [],
                pagination: {
                    ...this.state.pagination,
                    leaveBalances: {
                        count: response.data.count || 0,
                        next: response.data.next || null,
                        previous: response.data.previous || null,
                    },
                },
                loading: { ...this.state.loading, leaveBalances: false },
            });
        } else {
            this.setState({
                error: response.error || 'Failed to fetch leave balances',
                loading: { ...this.state.loading, leaveBalances: false },
            });
        }
    }

    // ==================== Leave Type Actions ====================
    setSelectedLeaveType(leaveType) {
        this.setState({ selectedLeaveType: leaveType });
    }

    selectLeaveTypeById(id) {
        const leaveType = this.state.leaveTypes.find(lt => lt.id === Number(id)) || null;
        this.setState({ selectedLeaveType: leaveType });
    }


    async deleteLeaveType(id) {
        this.setState({
            loading: { ...this.state.loading, leaveTypes: true },
            error: null,
        });

        const response = await this.apiCall(`/api/v1/leavetype/${id}/`, {
            method: 'DELETE',
        });

        if (response.success) {
            this.setState({
                leaveTypes: this.state.leaveTypes.filter(lt => lt.id !== id),
                selectedLeaveType: this.state.selectedLeaveType?.id === id 
                    ? null 
                    : this.state.selectedLeaveType,
                success: 'Leave type deleted successfully',
                loading: { ...this.state.loading, leaveTypes: false },
            });
            return true;
        } else {
            this.setState({
                error: response.error || 'Failed to delete leave type',
                loading: { ...this.state.loading, leaveTypes: false },
            });
            return false;
        }
    }

    // ==================== User Actions ====================
    setSelectedUserIds(userIds) {
        this.setState({ selectedUserIds: userIds });
    }

    toggleUserSelection(userId) {
        const userIds = this.state.selectedUserIds.includes(userId)
            ? this.state.selectedUserIds.filter(id => id !== userId)
            : [...this.state.selectedUserIds, userId];
        this.setState({ selectedUserIds: userIds });
    }

    clearUserSelection() {
        this.setState({ selectedUserIds: [] });
    }

    // ==================== Initialize Actions ====================
    async previewInitialization(leaveTypeId, year, userIds) {
        this.setState({
            loading: { ...this.state.loading, preview: true },
            error: null,
            success: null,
        });

        const request = {
            leave_type_id: leaveTypeId,
            year: year,
            preview_only: true,
        };

        if (userIds && userIds.length > 0) {
            request.user_ids = userIds;
        }

        const response = await this.apiCall('/api/v1/leave-balances/initialize/', {
            method: 'POST',
            body: JSON.stringify(request),
        });

        if (response.success) {
            this.setState({
                previewData: response.data,
                filteredPreviewData: response.data.data,
                loading: { ...this.state.loading, preview: false },
            });
        } else {
            this.setState({
                error: response.error || 'Failed to generate preview',
                loading: { ...this.state.loading, preview: false },
            });
        }
    }

    async executeInitialization(leaveTypeId, year, userIds) {
        this.setState({
            loading: { ...this.state.loading, execute: true },
            error: null,
            success: null,
        });

        const request = {
            leave_type_id: leaveTypeId,
            year: year,
            preview_only: false,
        };

        if (userIds && userIds.length > 0) {
            request.user_ids = userIds;
        }

        const response = await this.apiCall('/api/v1/leave-balances/initialize/', {
            method: 'POST',
            body: JSON.stringify(request),
        });

        if (response.success) {
            this.setState({
                success: response.data.message || 'Leave balances initialized successfully',
                previewData: null,
                filteredPreviewData: [],
                previewFilter: 'all',
                loading: { ...this.state.loading, execute: false },
            });

            // Refresh leave balances
            await this.fetchLeaveBalances({ year });
        } else {
            this.setState({
                error: response.error || 'Failed to initialize leave balances',
                loading: { ...this.state.loading, execute: false },
            });
        }
    }

    cancelPreview() {
        this.setState({
            previewData: null,
            filteredPreviewData: [],
            previewFilter: 'all',
        });
    }

    // ==================== Filter Actions ====================
    setPreviewFilter(filter) {
        this.setState({ previewFilter: filter });
        this.applyPreviewFilter();
    }

    setSelectedYear(year) {
        this.setState({ selectedYear: year });
    }

    applyPreviewFilter() {
        const { previewData, previewFilter } = this.state;

        if (!previewData) {
            this.setState({ filteredPreviewData: [] });
            return;
        }

        const filtered = previewFilter === 'all'
            ? previewData.data
            : previewData.data.filter(item => item.action === previewFilter);

        this.setState({ filteredPreviewData: filtered });
    }

    // ==================== UI Actions ====================
    setError(error) {
        this.setState({ error, success: null });
    }

    setSuccess(success) {
        this.setState({ success, error: null });
    }

    clearMessages() {
        this.setState({ error: null, success: null });
    }

    // ==================== Reset ====================
    reset() {
        this.state = {
            leaveTypes: [],
            selectedLeaveType: null,
            users: [],
            leaveBalances: [],
            previewData: null,
            filteredPreviewData: [],
            loading: {
                leaveTypes: false,
                users: false,
                leaveBalances: false,
                preview: false,
                execute: false,
            },
            error: null,
            success: null,
            previewFilter: 'all',
            selectedYear: new Date().getFullYear(),
            selectedUserIds: [],
            pagination: {
                leaveTypes: { count: 0, next: null, previous: null },
                users: { count: 0, next: null, previous: null },
                leaveBalances: { count: 0, next: null, previous: null },
            },
        };
        this.notify();
    }
}

// Export singleton instance
const leaveBalanceStore = new LeaveBalanceStore();
window.leaveBalanceStore = leaveBalanceStore;