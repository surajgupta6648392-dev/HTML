// LibraryMS small UI helpers
document.addEventListener("DOMContentLoaded", function () {
  // Mobile sidebar toggle
  var toggle = document.getElementById("sidebarToggle");
  var sidebar = document.getElementById("sidebar");
  if (toggle && sidebar) {
    toggle.addEventListener("click", function () {
      sidebar.classList.toggle("show");
    });
    // close sidebar when tapping outside on mobile
    document.addEventListener("click", function (e) {
      if (window.innerWidth < 768 &&
          sidebar.classList.contains("show") &&
          !sidebar.contains(e.target) &&
          !toggle.contains(e.target)) {
        sidebar.classList.remove("show");
      }
    });
  }

  // Auto-dismiss flash messages after 6 seconds
  setTimeout(function () {
    document.querySelectorAll(".alert-dismissible").forEach(function (el) {
      var alert = bootstrap.Alert.getOrCreateInstance(el);
      alert.close();
    });
  }, 6000);
});
