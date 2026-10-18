const form = document.getElementById("timetableForm");
const timetableBody = document.getElementById("timetableBody");
const emptyMessage = document.getElementById("emptyMessage");

const searchInput = document.getElementById("searchInput");
const editIdInput = document.getElementById("editId");

const submitBtn = document.getElementById("submitBtn");
const cancelEditBtn = document.getElementById("cancelEdit");
const formTitle = document.getElementById("formTitle");

const days = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday"
];

let timetable = [];

const fields = [
    "day",
    "subject",
    "teacher",
    "room",
    "startTime",
    "endTime"
];

// Load saved data
function loadData() {
    try {
        const savedData = localStorage.getItem("collegeTimetable");
        const parsedData = savedData ? JSON.parse(savedData) : [];

        timetable = Array.isArray(parsedData) ? parsedData : [];
    } catch (error) {
        timetable = [];
    }

    renderTimetable();
}

// Save data
function saveData() {
    try {
        localStorage.setItem(
            "collegeTimetable",
            JSON.stringify(timetable)
        );

        return true;
    } catch (error) {
        alert("Unable to save data in this browser.");
        return false;
    }
}

// Update dashboard
function updateDashboard() {
    document.getElementById("totalClasses").textContent =
        timetable.length;

    const subjects = new Set(
        timetable.map(item => item.subject.toLowerCase())
    );

    document.getElementById("totalSubjects").textContent =
        subjects.size;
}

// Check time conflicts
function hasConflict(newClass, excludedId = "") {
    return timetable.some(item => {
        if (item.id === excludedId) {
            return false;
        }

        return (
            item.day === newClass.day &&
            item.startTime < newClass.endTime &&
            item.endTime > newClass.startTime
        );
    });
}

// Render timetable
function renderTimetable() {
    const query = searchInput.value.trim().toLowerCase();

    const filteredData = timetable
        .filter(item =>
            item.subject.toLowerCase().includes(query) ||
            item.teacher.toLowerCase().includes(query) ||
            item.room.toLowerCase().includes(query)
        )
        .sort((a, b) => {
            const dayDifference =
                days.indexOf(a.day) - days.indexOf(b.day);

            if (dayDifference !== 0) {
                return dayDifference;
            }

            return a.startTime.localeCompare(b.startTime);
        });

    timetableBody.replaceChildren();

    emptyMessage.hidden = filteredData.length > 0;

    filteredData.forEach(item => {
        const row = document.createElement("tr");

        fields.forEach(field => {
            const cell = document.createElement("td");

            cell.textContent = item[field];
            row.appendChild(cell);
        });

        const actionCell = document.createElement("td");

        const editButton = document.createElement("button");
        editButton.textContent = "Edit";
        editButton.className = "edit-btn";

        editButton.addEventListener("click", () => {
            editClass(item.id);
        });

        const deleteButton = document.createElement("button");
        deleteButton.textContent = "Delete";
        deleteButton.className = "delete-btn";

        deleteButton.addEventListener("click", () => {
            deleteClass(item.id);
        });

        actionCell.append(editButton, deleteButton);
        row.appendChild(actionCell);

        timetableBody.appendChild(row);
    });

    updateDashboard();
}

// Reset form
function resetForm() {
    form.reset();
    editIdInput.value = "";

    formTitle.textContent = "Add New Class";
    submitBtn.textContent = "Add Class";
    cancelEditBtn.hidden = true;
}

// Add or update class
form.addEventListener("submit", function(event) {
    event.preventDefault();

    const classData = {
        id: editIdInput.value || (
            Date.now().toString() +
            Math.random().toString(16).slice(2)
        ),

        day: document.getElementById("day").value,
        subject: document.getElementById("subject").value.trim(),
        teacher: document.getElementById("teacher").value.trim(),
        room: document.getElementById("room").value.trim(),
        startTime: document.getElementById("startTime").value,
        endTime: document.getElementById("endTime").value
    };

    if (
        !classData.subject ||
        !classData.teacher ||
        !classData.room ||
        !classData.day ||
        !classData.startTime ||
        !classData.endTime
    ) {
        alert("Please fill in all fields.");
        return;
    }

    if (classData.startTime >= classData.endTime) {
        alert("End time must be later than start time.");
        return;
    }

    if (hasConflict(classData, editIdInput.value)) {
        alert("Time conflict! Another class exists in this time slot.");
        return;
    }

    const previousData = [...timetable];

    if (editIdInput.value) {
        timetable = timetable.map(item =>
            item.id === editIdInput.value ? classData : item
        );
    } else {
        timetable.push(classData);
    }

    if (!saveData()) {
        timetable = previousData;
        renderTimetable();
        return;
    }

    renderTimetable();
    resetForm();

    alert("Class saved successfully!");
});

// Edit class
function editClass(id) {
    const item = timetable.find(entry => entry.id === id);

    if (!item) {
        return;
    }

    editIdInput.value = item.id;

    fields.forEach(field => {
        document.getElementById(field).value = item[field];
    });

    formTitle.textContent = "Edit Class";
    submitBtn.textContent = "Update Class";
    cancelEditBtn.hidden = false;

    window.scrollTo({
        top: 0,
        behavior: "smooth"
    });
}

// Delete class
function deleteClass(id) {
    if (!confirm("Are you sure you want to delete this class?")) {
        return;
    }

    const previousData = [...timetable];

    timetable = timetable.filter(item => item.id !== id);

    if (!saveData()) {
        timetable = previousData;
        renderTimetable();
        return;
    }

    if (editIdInput.value === id) {
        resetForm();
    }

    renderTimetable();
}

// Cancel editing
cancelEditBtn.addEventListener("click", resetForm);

// Search
searchInput.addEventListener("input", renderTimetable);

// Initialize project
loadData();
