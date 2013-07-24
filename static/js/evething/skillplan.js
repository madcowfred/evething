EVEthing.skillplan = {
    // current skill popover displayed
    current_popover_id: false,
    
    addSkillInPlanUrl: "",
    
    onload: function() {
        // hover thing for skill descriptions
        $('.skill-list-hover').popover({ 
            animation: false, 
            trigger: 'click', 
            html: true,
            placement: 'left',
            container: 'body'
        }).on('click', 
            function() {
                // popover on click, but only display one popover.
                if(EVEthing.skillplan.current_popover_id) {
                    if(EVEthing.skillplan.current_popover_id != $(this).attr('id')) {
                        $('#'+EVEthing.skillplan.current_popover_id).popover('hide');
                    }
                }
                EVEthing.skillplan.current_popover_id=$(this).attr('id');
                
                // define click events on button in the popover        
                $('.btn-plan-skill').on('click',
                    function() {
                        var plan_to_level   = $(this).attr('data-level');
                        var plan_skill_id   = $(this).attr('data-id');
                        EVEthing.skillplan.addSkillInPlan(plan_skill_id, plan_to_level);
                        return false;
                    }
                );
                return false;
            }
        );
        
    },
    
    addRemapPoint: function() {
        return false;
    },
    
    addSkillInPlan: function(skill_id, level) {
        $.ajax({
            crossDomain: false,
            url: EVEthing.skillplan.addSkillInPlanUrl,
            data: { skill_id:skill_id
                  , skill_level:level
                  , skillplan_id:EVEthing.skillplan.skillplanId },
            type:'post',
            beforeSend: function(xhr, settings) {
                xhr.setRequestHeader("X-CSRFToken", $.cookie('csrftoken'));
            },
            success: function(json) {
                response = $.parseJSON(json);
                if(response.status == "ok"){
                    $('#'+EVEthing.skillplan.current_popover_id).popover('hide');
                    EVEthing.skillplan.reload();
                }
            },
            error: function(xhr, status, error) {
                // display the error for the user (at least !)
            }
        });
    },
    
    reload: function() {
        // call a page with a $.get to grab the skillplan entries.
    }
    
    optimizeAttributes: function() {
    
    },
    
    optimizeRemaps: function() {
    
    },

}
