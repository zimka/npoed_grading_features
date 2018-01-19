from xmodule.modulestore.tests.factories import CourseFactory, ItemFactory
from lms.djangoapps.grades.tests.utils import answer_problem
from ..models import NpoedGradingFeatures


class BuildCourseMixin(object):
    """
    Mixin with methods to build, validate and grade course
    represented by tree
    """
    def _build_from_tree(self, tree):
        """
        Builds course from tree. Tree is stored in dict in a view like this:
        {
            "SectionName1":{
                "SubsectionName11_or_smth_else":("assignment_category" if graded, {
                    "BlockName111":(weight or None(means 'html'), {
                        "ProblemOrHtmlName":(earn, max)
                    }
                })
            }
        }
        """
        course = self.course
        request = self.request
        to_answer = []
        for section_name, section_tree in tree.iteritems():
            current_section = ItemFactory.create(parent=course, category="chapter", display_name=section_name)
            for subsection_name, subsection_pair in section_tree.iteritems():
                assignment_category, subsection_tree = subsection_pair
                current_subsection = ItemFactory.create(
                    parent=current_section,
                    category="sequential",
                    display_name=subsection_name,
                    graded=assignment_category is not None,
                    format=assignment_category or ""
                )
                for unit_name, unit_pair in subsection_tree.iteritems():
                    weight, unit_tree = unit_pair
                    metadata = {} if (weight is None) else {"weight": weight}
                    current_unit = ItemFactory.create(parent=current_subsection, category="vertical",
                                                      display_name=unit_name, metadata=metadata)
                    for problem_name, problem_pair in unit_tree.iteritems():
                        earned, max_ = problem_pair

                        kwargs = {
                            "parent": current_unit,
                            "display_name": problem_name,
                            "category": "html" if max_ is None else "problem"
                        }
                        if assignment_category and not (max is None):
                            kwargs["format"] = assignment_category
                        current_problem = ItemFactory.create(**kwargs)
                        if not (earned is None):
                            to_answer.append((current_problem, (earned, max_)))
        # Somehow 'answer_problem' must be after course building, otherwise
        # items not created
        for problem, pair in to_answer:
            earned, max_ = pair
            answer_problem(course, request, problem, score=earned, max_value=max_)

    def _check_tree(self, tree, course=None):
        if course is None:
            course = self.course
        message = "Check tree failed: {} '{}' not found. Have names: {}"
        for section_name, section_tree in tree.iteritems():
            sections = course.get_children()
            current_section = [x for x in sections if x.display_name == section_name]
            if not len(current_section):
                raise ValueError(message.format('section', section_name), [x.display_name for x in sections])
            current_section = current_section[0]
            for subsection_name, subsection_pair in section_tree.iteritems():
                assignment_category, subsection_tree = subsection_pair
                subsections = current_section.get_children()
                current_subsection = [x for x in subsections if x.display_name == subsection_name]
                if not len(current_subsection):
                    raise ValueError(message.format('subsection', subsection_name),
                                     [x.display_name for x in subsections])
                current_subsection = current_subsection[0]
                for unit_name, unit_pair in subsection_tree.iteritems():
                    weight, unit_tree = unit_pair
                    units = current_subsection.get_children()
                    current_unit = [x for x in units if x.display_name == unit_name]
                    if not len(current_unit):
                        raise ValueError(message.format('unit', unit_name, [x.display_name for x in units]))
                    current_unit = current_unit[0]
                    for problem_name, problem_pair in unit_tree.iteritems():
                        problems = current_unit.get_children()
                        current_problem = [x for x in problems if x.display_name == problem_name]
                        if not len(current_problem):
                            raise ValueError(
                                message.format('problem', problem_name, [x.display_name for x in problems]))

    def _update_grading_policy(self, grading_policy=None):
        if grading_policy is None:
            grading_policy = {
                "GRADER": [
                    {
                        "type": "Homework",
                        "min_count": 1,
                        "drop_count": 0,
                        "short_label": "HW",
                        "weight": 1.0,
                    },
                ],
                "GRADE_CUTOFFS": {
                    "Pass": 0.5,
                },
            }

        self.course.set_grading_policy(grading_policy)
        self.store.update_item(self.course, 0)
        self.course = self.store.get_course(self.course.id)

    def _grade_tree(self, tree, enable_vertical):
        self.course = self.store.get_course(self.course.id)

        def get_unit_problem_pairs(unit_tree):
            all_earned, all_max = [], []
            for _, pair in unit_tree.iteritems():
                earned, max_ = pair
                if not (earned is None or max_ is None):
                    all_earned.append(float(earned))
                    all_max.append(float(max_))
            return all_earned, all_max

        def grade_subsection(subsection_tree):
            element_earned, element_max = [], []

            for unit_name, unit_pair in subsection_tree.iteritems():
                weight, unit_tree = unit_pair
                current_earned, current_max = get_unit_problem_pairs(unit_tree)
                if not current_max:
                    continue
                if enable_vertical:
                    if not weight:
                        continue
                    current_earned = [sum(current_earned)*weight/sum(current_max)]
                    current_max = [weight]
                element_earned.extend(current_earned)
                element_max.extend(current_max)
            if not element_max:
                return None
            return zip(element_earned, element_max)

        def compute_subsection_percent(pairs):
            if pairs:
                return sum(x[0] for x in pairs) / sum(x[1] for x in pairs)

        def drop_minimal_vertical_from_subsection_grades_mimic(tuple_of_subsection_unit_score_pairs):
            """
            :param tuple_of_subsection_unit_score_pairs_lists:
                (
                    [(1,3), (0,1), (None, None)],
                    [(1,1, (1,10)]
                )
                Drops (1,10) because have lost 9 points
            """
            max_lost_points = -1
            max_lost_points_index = (-1, "None")
            for num_ss, subsection_grades in enumerate(tuple_of_subsection_unit_score_pairs):
                for num_p, pair in enumerate(subsection_grades):
                    if not pair[1]:
                        continue
                    lost_points = pair[1] - pair[0]
                    if lost_points > max_lost_points:
                        max_lost_points = lost_points
                        max_lost_points_index = (num_ss, num_p)
            if max_lost_points == -1:
                return
            tuple_of_subsection_unit_score_pairs[max_lost_points_index[0]].pop(max_lost_points_index[1])

        score_by_assignment_category = {}
        for _, section_tree in tree.iteritems():
            for __, subsection_pair in section_tree.iteritems():
                assignment_category, subsection_tree = subsection_pair
                if not assignment_category:
                    continue
                if assignment_category not in score_by_assignment_category:
                    score_by_assignment_category[assignment_category] = []
                subsection_score = grade_subsection(subsection_tree)
                if subsection_score is not None:
                    score_by_assignment_category[assignment_category].append(subsection_score)
        course_score = 0
        assignment_category_meta = dict(
            ((x["type"], {"weight": x["weight"], "drop_count": x["drop_count"]})
            for x in self.course.grading_policy["GRADER"])
        )
        for assignment_category in score_by_assignment_category:
            if enable_vertical:
                for _ in range(int(assignment_category_meta[assignment_category]["drop_count"])):
                    drop_minimal_vertical_from_subsection_grades_mimic(score_by_assignment_category[assignment_category])
            subsection_percents = [compute_subsection_percent(x) for x in score_by_assignment_category[assignment_category]]
            subsection_percents = sorted(subsection_percents, key=lambda x: -1 if x is None else x)
            if not enable_vertical:
                start_id = assignment_category_meta[assignment_category]["drop_count"]
                subsection_percents = subsection_percents[start_id::]

            if subsection_percents:
                weight = assignment_category_meta[assignment_category]["weight"]
                average_score = sum(subsection_percents)/len(subsection_percents)
                assignment_score = weight * average_score
                course_score += assignment_score

        course_score = round(course_score * 100 + 0.05) / 100
        return course_score

    def _enable_if_needed(self, enable_vertical):
        if enable_vertical:
            NpoedGradingFeatures.enable_vertical_grading(str(self.course.id))