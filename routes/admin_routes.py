from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from models import db, Sport, Department, Team, Tournament

admin_bp = Blueprint('admin', __name__)


@admin_bp.route('/admin')
def event_config():
    sports = Sport.query.filter_by(is_active=True).order_by(Sport.id).all()
    departments = Department.query.filter_by(is_active=True).order_by(Department.id).all()
    tournaments = Tournament.query.all()
    teams = Team.query.all()

    return render_template(
        'admin/config.html',
        sports=sports,
        departments=departments,
        tournaments=tournaments,
        teams=teams,
    )


@admin_bp.route('/admin/sports/<int:sport_id>/update', methods=['POST'])
def update_sport_categories(sport_id):
    sport = Sport.query.get_or_404(sport_id)
    # Checkbox values for categories
    selected_cats = request.form.getlist('categories')
    if not selected_cats:
        flash('At least one category (Boys or Girls) must be selected for a sport.', 'danger')
        return redirect(url_for('admin.event_config'))

    sport.categories = ','.join(selected_cats)
    
    # Optional points/draws updates if provided
    try:
        if 'points_win' in request.form:
            sport.points_win = int(request.form.get('points_win', sport.points_win))
        if 'points_draw' in request.form:
            sport.points_draw = int(request.form.get('points_draw', sport.points_draw))
        if 'points_loss' in request.form:
            sport.points_loss = int(request.form.get('points_loss', sport.points_loss))
    except (ValueError, TypeError):
        pass

    db.session.commit()
    flash(f'Updated categories for {sport.name}: {", ".join(selected_cats)}', 'success')
    return redirect(url_for('admin.event_config'))


@admin_bp.route('/admin/sports/add', methods=['POST'])
def add_sport():
    name = request.form.get('name', '').strip()
    code = request.form.get('code', '').strip().lower()
    icon = request.form.get('icon', '🏆').strip()
    result_mode = request.form.get('result_mode', 'score_based').strip()
    categories_list = request.form.getlist('categories')

    if not name:
        flash('Sport name is required.', 'danger')
        return redirect(url_for('admin.event_config'))

    if not code:
        code = name.lower().replace(' ', '_')

    existing = Sport.query.filter_by(code=code).first()
    if existing:
        flash(f'Sport with code "{code}" already exists.', 'danger')
        return redirect(url_for('admin.event_config'))

    cats_str = ','.join(categories_list) if categories_list else 'Boys,Girls'

    new_sport = Sport(
        name=name,
        code=code,
        icon=icon or '🏆',
        result_mode=result_mode,
        categories=cats_str,
    )
    db.session.add(new_sport)
    db.session.commit()
    flash(f'Sport "{name}" added successfully.', 'success')
    return redirect(url_for('admin.event_config'))


@admin_bp.route('/admin/sports/<int:sport_id>/delete', methods=['POST'])
def delete_sport(sport_id):
    sport = Sport.query.get_or_404(sport_id)
    # Check if any tournament is using this sport
    in_use = Tournament.query.filter_by(sport_type=sport.code).first()
    if in_use:
        flash(f'Cannot delete sport "{sport.name}" because tournaments currently use it.', 'danger')
        return redirect(url_for('admin.event_config'))

    db.session.delete(sport)
    db.session.commit()
    flash(f'Sport "{sport.name}" deleted successfully.', 'success')
    return redirect(url_for('admin.event_config'))


@admin_bp.route('/admin/departments/add', methods=['POST'])
def add_department():
    code = request.form.get('code', '').strip().upper()
    name = request.form.get('name', '').strip()

    if not code or not name:
        flash('Department code and name are required.', 'danger')
        return redirect(url_for('admin.event_config'))

    existing = Department.query.filter_by(code=code).first()
    if existing:
        flash(f'Department "{code}" already exists.', 'danger')
        return redirect(url_for('admin.event_config'))

    new_dept = Department(code=code, name=name)
    db.session.add(new_dept)
    db.session.commit()
    flash(f'Department "{code} - {name}" added successfully.', 'success')
    return redirect(url_for('admin.event_config'))


@admin_bp.route('/admin/departments/<int:dept_id>/delete', methods=['POST'])
def delete_department(dept_id):
    dept = Department.query.get_or_404(dept_id)
    in_use = Team.query.filter_by(department=dept.code).first()
    if in_use:
        flash(f'Cannot delete department "{dept.code}" because registered teams/participants belong to it.', 'danger')
        return redirect(url_for('admin.event_config'))

    db.session.delete(dept)
    db.session.commit()
    flash(f'Department "{dept.code}" deleted successfully.', 'success')
    return redirect(url_for('admin.event_config'))


@admin_bp.route('/admin/clear-data', methods=['POST'])
def clear_all_data():
    """Wipe all tournaments, teams, matches, and standings so the admin can start fresh."""
    try:
        from models import Match, StandingEntry
        StandingEntry.query.delete()
        Match.query.delete()
        Team.query.delete()
        Tournament.query.delete()
        db.session.commit()
        flash('All tournaments, teams, fixtures, and scores have been wiped. The site is fresh!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error clearing data: {str(e)}', 'danger')
    return redirect(url_for('admin.event_config'))


@admin_bp.route('/participants')
def participants_directory():
    sport_filter = request.args.get('sport', '').strip().lower()
    gender_filter = request.args.get('gender', '').strip()
    dept_filter = request.args.get('department', '').strip().upper()
    search_q = request.args.get('q', '').strip().lower()

    query = Team.query.join(Tournament)

    if sport_filter and sport_filter != 'all':
        query = query.filter(
            (Team.sport_type == sport_filter) |
            (Team.sport_type.is_(None) & (Tournament.sport_type == sport_filter))
        )

    if gender_filter and gender_filter.lower() != 'all':
        query = query.filter(
            (Team.gender == gender_filter) |
            (Team.gender.is_(None) & (Tournament.gender == gender_filter))
        )

    if dept_filter and dept_filter != 'ALL':
        query = query.filter(Team.department == dept_filter)

    all_teams = query.order_by(Team.created_at.desc()).all()

    if search_q:
        all_teams = [
            t for t in all_teams
            if search_q in t.name.lower() or
               (t.player_name and search_q in t.player_name.lower()) or
               (t.department and search_q in t.department.lower())
        ]

    sports = Sport.query.filter_by(is_active=True).all()
    departments = Department.query.filter_by(is_active=True).all()
    setup_tournaments = Tournament.query.filter_by(status='setup').order_by(Tournament.created_at.desc()).all()
    all_tournaments = Tournament.query.order_by(Tournament.created_at.desc()).all()

    return render_template(
        'participants.html',
        teams=all_teams,
        sports=sports,
        departments=departments,
        setup_tournaments=setup_tournaments,
        all_tournaments=all_tournaments,
        sport_filter=sport_filter or 'all',
        gender_filter=gender_filter or 'all',
        dept_filter=dept_filter or 'ALL',
        search_q=search_q,
    )


@admin_bp.route('/participants/add', methods=['POST'])
def add_participant():
    tournament_id = request.form.get('tournament_id', type=int)
    name = request.form.get('team_name', '').strip()
    department = request.form.get('department', 'CSE').strip().upper()
    gender = request.form.get('gender', 'Boys').strip()
    player_name = request.form.get('player_name', '').strip() or None

    if not tournament_id or not name:
        flash('Tournament selection and participant name are required.', 'danger')
        return redirect(url_for('admin.participants_directory'))

    tournament = Tournament.query.get_or_404(tournament_id)
    if not tournament.is_setup():
        flash('Cannot add participants to a tournament whose fixtures have already been generated.', 'warning')
        return redirect(url_for('admin.participants_directory'))

    name_key = name.lower()
    if Team.query.filter_by(tournament_id=tournament_id, name_key=name_key).first():
        flash(f'A participant named "{name}" already exists in {tournament.name}.', 'warning')
        return redirect(url_for('admin.participants_directory'))

    new_team = Team(
        tournament_id=tournament_id,
        name=name,
        name_key=name_key,
        department=department,
        gender=gender,
        sport_type=tournament.sport_type,
        player_name=player_name,
    )
    db.session.add(new_team)
    db.session.commit()
    flash(f'Participant "{name}" ({department}, {gender}) registered for {tournament.name} successfully!', 'success')
    return redirect(url_for('admin.participants_directory'))


@admin_bp.route('/api/sports/<sport_code>/categories')
def api_sport_categories(sport_code):
    sport = Sport.query.filter_by(code=sport_code).first()
    if sport:
        return jsonify({
            'code': sport.code,
            'name': sport.name,
            'categories': sport.get_categories(),
            'result_mode': sport.result_mode,
            'points_win': sport.points_win,
            'points_draw': sport.points_draw,
            'points_loss': sport.points_loss,
            'draws_allowed': sport.draws_allowed,
        })
    # Default fallback
    return jsonify({
        'code': sport_code,
        'name': sport_code.title(),
        'categories': ['Boys', 'Girls'],
        'result_mode': 'score_based',
        'points_win': 3,
        'points_draw': 1,
        'points_loss': 0,
        'draws_allowed': True,
    })
