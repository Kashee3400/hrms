$(document).ready(function () {
    calculateDuration();
    // Field references (you can replace these with your actual input field selectors)
    const fromField = document.getElementById("id_from_date");
    const toField = document.getElementById("id_to_date");
    const durationField = document.getElementById("id_reg_duration");

    $('#id_reg_status input[type="radio"]').on('change', function () {
        var selected = $(this).val();
        console.log("regStatus: " + selected);
    
        // Clear fields before setting new values
        fromField.value = "";
        toField.value = "";
        durationField.value = "";
    
        // Handle data population based on selection
        if (selected === "late coming") {
            const data = JSON.parse(document.getElementById("late-coming-data").textContent);
    
            // Format dates to a standard string if needed (you can customize this)
            const fromDate = new Date(data.from_date);
            const toDate = new Date(data.to_date);
            const duration = data.duration;
    
            // Format dates to 'YYYY-MM-DD HH:mm:ss'
            const fromDateFormatted = formatDate(fromDate);
            const toDateFormatted = formatDate(toDate);
    
            // Set the values into the fields
            fromField.value = fromDateFormatted;  // Format: YYYY-MM-DD HH:mm:ss
            toField.value = toDateFormatted;      // Format: YYYY-MM-DD HH:mm:ss
            durationField.value = duration;  // e.g. "0:43" or whatever format is returned
        } else if (selected === "early going") {
            const data = JSON.parse(document.getElementById("early-going-data").textContent);
    
            // Format dates to a standard string if needed
            const fromDate = new Date(data.from_date);
            const toDate = new Date(data.to_date);
            const duration = data.duration;
    
            // Format dates to 'YYYY-MM-DD HH:mm:ss'
            const fromDateFormatted = formatDate(fromDate);
            const toDateFormatted = formatDate(toDate);
    
            // Set the values into the fields
            fromField.value = fromDateFormatted;  // Format: YYYY-MM-DD HH:mm:ss
            toField.value = toDateFormatted;      // Format: YYYY-MM-DD HH:mm:ss
            durationField.value = duration;  // e.g. "0:11" or whatever format is returned
        }
    });
    
    // Helper function to format the date to 'YYYY-MM-DD HH:mm:ss'
    function formatDate(date) {
        const year = date.getFullYear();
        const month = String(date.getMonth() + 1).padStart(2, '0'); // Months are 0-based
        const day = String(date.getDate()).padStart(2, '0');
        const hours = String(date.getHours()).padStart(2, '0');
        const minutes = String(date.getMinutes()).padStart(2, '0');
        const seconds = String(date.getSeconds()).padStart(2, '0');
    
        return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`;
    }
    
    // Function to calculate the difference between two datetime fields
    function calculateDuration() {
        var fromDate = $('#id_from_date').val();
        var toDate = $('#id_to_date').val();
        if (fromDate && toDate) {
            var fromDateTime = new Date(fromDate);
            var toDateTime = new Date(toDate);
            if (fromDateTime <= toDateTime) {
                var diffMs = toDateTime - fromDateTime; // Difference in milliseconds
                var diffHours = Math.floor(diffMs / (1000 * 60 * 60));
                var diffMinutes = Math.floor((diffMs % (1000 * 60 * 60)) / (1000 * 60));
                var duration = diffHours + ':' + diffMinutes;
                $('#id_reg_duration').val(duration);
            } else {
                alert('From Date cannot be later than To Date.');
                $('#id_reg_duration').val('');
            }
        }
    }
    $(document).on('dp.change', function () {
        calculateDuration();
    });
});
