
document.addEventListener('DOMContentLoaded', function() {
  const toggleButton = document.querySelector('.navbar .toggle-button');
  const navbarLinks = document.querySelector('.navbar .nav-links');

  toggleButton.addEventListener('click', function() {
    navbarLinks.classList.toggle('active');
  });
});

