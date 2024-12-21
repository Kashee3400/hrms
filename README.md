    {% comment %} <li class="nav-item {% if (request.user.is_superuser and request.path == '/admin/') or (not request.user.is_superuser and request.path == '/') %} active {% endif %}">
      {% if request.user.is_superuser %}
        <a class="nav-link" href="{% url 'admin:index' %}">
      {% else %}
        <a class="nav-link" href="/">
      {% endif %}
          <i class="mdi mdi-grid-large menu-icon"></i>
          <span class="menu-title">{% trans "Dashboard" %}</span>
        </a>
    </li>   {% endcomment %}