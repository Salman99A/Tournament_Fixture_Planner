from datetime import date

from flask import Blueprint, render_template, request, redirect, url_for, flash
from models import db, Tournament, Team, Match, StandingEntry, Sport, Department
from models import SPORT_RESULT_MODE, RESULT_MODE_SCORE, RESULT_MODE_WINNER, VALID_SPORTS
from fixture_engine import (
    generate_round_robin_fixtures,
    generate_knockout_fixtures,
    validate_teams,
)
from scheduler import schedule_round_robin, clear_pending_schedule

tournament_bp = Blueprint('tournament', __name__)


@tournament_bp.route('/')
def index():
    sport_filter  = request.args.get('sport', '').strip().lower()
    gender_filter = request.args.get('gender', '').strip()
    dept_filter   = request.args.get('department', '').strip().upper()
    format_filter = request.args.get('format', '').strip()
    status_filter = request.args.get('status', '').strip()

    q = Tournament.query

    if sport_filter and sport_filter != 'all':
        q = q.filter_by(sport_type=sport_filter)
    if gender_filter and gender_filter.lower() != 'all':
        q = q.filter_by(gender=gender_filter)
    if dept_filter and dept_filter != 'ALL':
        q = q.filter_by(department=dept_filter)
    if format_filter and format_filter in ['round_robin', 'knockout']:
        q = q.filter_by(format=format_filter)
    if status_filter and status_filter in ['setup', 'active', 'completed']:
        q = q.filter_by(status=status_filter)

    tournaments = q.order_by(Tournament.created_at.desc()).all()
    sports = Sport.query.filter_by(is_active=True).all()
    departments = Department.query.filter_by(is_active=True).all()

    return render_template(
        'index.html',
        tournaments=tournaments,
        sports=sports,
        departments=departments,
        sport_filter=sport_filter or 'all',
        gender_filter=gender_filter or 'all',
        dept_filter=dept_filter or 'ALL',
        format_filter=format_filter,
        status_filter=status_filter,
    )


@tournament_bp.route('/tournament/create', methods=['GET', 'POST'])
def create_tournament():
    sports = Sport.query.filter_by(is_active=True).all()
    departments = Department.query.filter_by(is_active=True).all()

    if request.method == 'POST':
        name       = request.form.get('name', '').strip()
        fmt        = request.form.get('format', '').strip()
        sport_type = request.form.get('sport_type', 'cricket').strip().lower()
        gender     = request.form.get('gender', 'Boys').strip()
        department = request.form.get('department', 'All').strip()

        if not name:
            flash('Tournament name is required.', 'danger')
            return render_template('create_tournament.html', today=_today_str(), sports=sports, departments=departments)

        if fmt not in ['round_robin', 'knockout']:
            flash('Please select a valid format.', 'danger')
            return render_template('create_tournament.html', today=_today_str(), sports=sports, departments=departments)

        # Check sport in DB or fallback
        sport_record = Sport.query.filter_by(code=sport_type).first()
        if sport_record:
            result_mode = sport_record.result_mode
            default_win, default_draw, default_loss = sport_record.points_win, sport_record.points_draw, sport_record.points_loss
        else:
            if sport_type not in VALID_SPORTS:
                sport_type = 'generic'
            result_mode = SPORT_RESULT_MODE.get(sport_type, RESULT_MODE_SCORE)
            if result_mode == RESULT_MODE_WINNER:
                default_win, default_draw, default_loss = 2, 1, 0
            else:
                default_win, default_draw, default_loss = 3, 1, 0

        try:
            pts_win  = int(request.form.get('points_win',  default_win))
            pts_draw = int(request.form.get('points_draw', default_draw))
            pts_loss = int(request.form.get('points_loss', default_loss))
        except (ValueError, TypeError):
            pts_win, pts_draw, pts_loss = default_win, default_draw, default_loss

        draws_allowed = (fmt == 'round_robin')

        sched_start = None
        sched_end   = None
        sched_rest  = 2

        if fmt == 'round_robin':
            raw_start = request.form.get('sched_start_date', '').strip()
            raw_end   = request.form.get('sched_end_date',   '').strip()
            raw_rest  = request.form.get('sched_min_rest',   '2').strip()

            if raw_start:
                try:
                    sched_start = date.fromisoformat(raw_start)
                except ValueError:
                    flash('Invalid start date — scheduling config ignored.', 'warning')

            if sched_start and raw_end:
                try:
                    sched_end = date.fromisoformat(raw_end)
                    if sched_end <= sched_start:
                        flash('End date must be after start date. Using default (+60 days).', 'warning')
                        sched_end = None
                except ValueError:
                    pass

            try:
                sched_rest = max(1, int(raw_rest))
            except (ValueError, TypeError):
                sched_rest = 2

        tournament = Tournament(
            name=name,
            format=fmt,
            sport_type=sport_type,
            gender=gender,
            department=department or 'All',
            result_mode=result_mode,
            points_win=pts_win,
            points_draw=pts_draw,
            points_loss=pts_loss,
            draws_allowed=draws_allowed,
            sched_start_date=sched_start,
            sched_end_date=sched_end,
            sched_min_rest=sched_rest,
        )
        db.session.add(tournament)
        db.session.commit()

        flash(f'Tournament "{name}" created! Now add your teams.', 'success')
        return redirect(url_for('team.manage_teams', tournament_id=tournament.id))

    return render_template('create_tournament.html', today=_today_str(), sports=sports, departments=departments)


@tournament_bp.route('/tournament/<int:tournament_id>/edit', methods=['GET', 'POST'])
def edit_tournament(tournament_id):
    tournament = Tournament.query.get_or_404(tournament_id)
    if not tournament.is_setup():
        flash('Tournament settings cannot be modified after fixtures have been generated.', 'warning')
        return redirect(url_for('match.fixtures', tournament_id=tournament_id))

    sports = Sport.query.filter_by(is_active=True).all()
    departments = Department.query.filter_by(is_active=True).all()

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        fmt = request.form.get('format', '').strip()
        sport_type = request.form.get('sport_type', tournament.sport_type).strip().lower()
        gender = request.form.get('gender', tournament.gender).strip()
        department = request.form.get('department', tournament.department).strip()

        if not name:
            flash('Tournament name is required.', 'danger')
            return render_template('edit_tournament.html', tournament=tournament, sports=sports, departments=departments)

        if fmt not in ['round_robin', 'knockout']:
            flash('Please select a valid format.', 'danger')
            return render_template('edit_tournament.html', tournament=tournament, sports=sports, departments=departments)

        sport_record = Sport.query.filter_by(code=sport_type).first()
        if sport_record:
            result_mode = sport_record.result_mode
        else:
            result_mode = SPORT_RESULT_MODE.get(sport_type, RESULT_MODE_SCORE)

        try:
            pts_win = int(request.form.get('points_win', tournament.points_win))
            pts_draw = int(request.form.get('points_draw', tournament.points_draw))
            pts_loss = int(request.form.get('points_loss', tournament.points_loss))
        except (ValueError, TypeError):
            pts_win, pts_draw, pts_loss = tournament.points_win, tournament.points_draw, tournament.points_loss

        tournament.name = name
        tournament.format = fmt
        tournament.sport_type = sport_type
        tournament.gender = gender
        tournament.department = department
        tournament.result_mode = result_mode
        tournament.points_win = pts_win
        tournament.points_draw = pts_draw
        tournament.points_loss = pts_loss
        tournament.draws_allowed = (fmt == 'round_robin')

        for t in tournament.teams:
            t.sport_type = sport_type
            if not t.gender:
                t.gender = gender

        db.session.commit()
        flash(f'Settings for "{tournament.name}" updated successfully.', 'success')
        return redirect(url_for('team.manage_teams', tournament_id=tournament.id))

    return render_template('edit_tournament.html', tournament=tournament, sports=sports, departments=departments)


@tournament_bp.route('/tournament/<int:tournament_id>')
def view_tournament(tournament_id):
    Tournament.query.get_or_404(tournament_id)
    return redirect(url_for('standings.progress', tournament_id=tournament_id))


@tournament_bp.route('/tournament/<int:tournament_id>/delete', methods=['POST'])
def delete_tournament(tournament_id):
    tournament = Tournament.query.get_or_404(tournament_id)
    name = tournament.name
    db.session.delete(tournament)
    db.session.commit()
    flash(f'Tournament "{name}" deleted.', 'info')
    return redirect(url_for('tournament.index'))


@tournament_bp.route('/tournament/<int:tournament_id>/generate', methods=['POST'])
def generate_fixtures(tournament_id):
    tournament = Tournament.query.get_or_404(tournament_id)

    if not tournament.is_setup():
        flash('Fixtures already generated for this tournament.', 'warning')
        return redirect(url_for('match.fixtures', tournament_id=tournament_id))

    teams      = Team.query.filter_by(tournament_id=tournament_id).all()
    team_names = [t.name for t in teams]

    is_valid, error = validate_teams(team_names)
    if not is_valid:
        flash(error, 'danger')
        return redirect(url_for('team.manage_teams', tournament_id=tournament_id))

    if tournament.format == 'round_robin':
        _generate_round_robin(tournament, teams)
        _init_standings(tournament, teams)
    else:
        _generate_knockout(tournament, teams)

    tournament.status = 'active'
    db.session.commit()

    # Auto-schedule inline (avoids redirect to POST-only route)
    if tournament.format == 'round_robin' and tournament.sched_start_date:
        _run_scheduler(tournament)
        db.session.commit()

    flash('Fixtures generated successfully!', 'success')
    return redirect(url_for('match.fixtures', tournament_id=tournament_id))


@tournament_bp.route('/tournament/<int:tournament_id>/schedule', methods=['POST'])
def run_schedule(tournament_id):
    tournament = Tournament.query.get_or_404(tournament_id)

    if tournament.format != 'round_robin':
        flash('Auto-scheduling is only available for Round Robin tournaments.', 'warning')
        return redirect(url_for('match.fixtures', tournament_id=tournament_id))

    if tournament.is_setup():
        flash('Generate fixtures first before scheduling.', 'warning')
        return redirect(url_for('team.manage_teams', tournament_id=tournament_id))

    raw_override = request.form.get('sched_start_override', '').strip()
    if raw_override:
        try:
            tournament.sched_start_date = date.fromisoformat(raw_override)
            db.session.commit()
        except ValueError:
            flash('Invalid date format — using saved start date.', 'warning')

    if not tournament.sched_start_date:
        tournament.sched_start_date = date.today()
        db.session.commit()

    _run_scheduler(tournament)
    db.session.commit()

    return redirect(url_for('match.fixtures', tournament_id=tournament_id))


# ─────────────────────────────────────────────────────────────────────────────
# Scheduling helper — shared by generate_fixtures and run_schedule
# ─────────────────────────────────────────────────────────────────────────────

def _run_scheduler(tournament):
    """
    Clear non-locked pending schedules and re-run the IPL-style daily spread
    scheduler. Manually-locked matches are preserved.
    Flashes summary messages.
    """
    all_matches = (
        Match.query
        .filter_by(tournament_id=tournament.id, is_bye=False)
        .order_by(Match.round_number, Match.match_number)
        .all()
    )

    locked_count = sum(1 for m in all_matches if m.manual_locked)

    # Only clear 'scheduled' non-locked matches — never touch completed or locked
    clear_pending_schedule(all_matches)

    scheduled, unscheduled = schedule_round_robin(
        all_matches,
        start_date=tournament.sched_start_date,
        end_date=tournament.sched_end_date,
        min_rest_days=tournament.sched_min_rest or 2,
    )

    lock_note = f' ({locked_count} manually locked match(es) preserved.)' if locked_count else ''

    if unscheduled == 0:
        flash(
            f'All {scheduled} match(es) scheduled using IPL-style daily spread '
            f'(weekdays: 7:30 PM · weekends: 3:30 PM & 7:30 PM).{lock_note}',
            'success',
        )
    elif scheduled == 0:
        flash(
            f'No matches could be scheduled. '
            f'Try adjusting the start date or minimum rest days.{lock_note}',
            'danger',
        )
    else:
        flash(
            f'{scheduled} match(es) scheduled. '
            f'⚠️  {unscheduled} match(es) could not be placed within the date range '
            f'and rest constraints — they remain unscheduled.{lock_note}',
            'warning',
        )


# ─────────────────────────────────────────────────────────────────────────────
# Fixture generation helpers
# ─────────────────────────────────────────────────────────────────────────────

def _generate_round_robin(tournament, teams):
    rounds = generate_round_robin_fixtures(teams)
    for round_idx, round_matches in enumerate(rounds, start=1):
        for match_idx, (team1, team2) in enumerate(round_matches, start=1):
            is_bye = (team1 is None or team2 is None)
            db.session.add(Match(
                tournament_id=tournament.id,
                round_number=round_idx,
                match_number=match_idx,
                team1_id=team1.id if team1 else None,
                team2_id=team2.id if team2 else None,
                is_bye=is_bye,
                status='completed' if is_bye else 'pending',
            ))


def _generate_knockout(tournament, teams):
    fixtures = generate_knockout_fixtures(teams)
    for match_idx, (team1, team2) in enumerate(fixtures, start=1):
        is_bye = (team2 is None)
        db.session.add(Match(
            tournament_id=tournament.id,
            round_number=1,
            match_number=match_idx,
            team1_id=team1.id if team1 else None,
            team2_id=team2.id if team2 else None,
            is_bye=is_bye,
            winner_id=team1.id if is_bye else None,
            status='completed' if is_bye else 'pending',
        ))


def _init_standings(tournament, teams):
    for team in teams:
        db.session.add(StandingEntry(
            tournament_id=tournament.id,
            team_id=team.id,
        ))


def _today_str():
    return date.today().isoformat()
